"""
Enhanced Smartsheet Extractor with Production Features
Robust extraction with validation, error handling, and monitoring
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timezone

from playwright.async_api import Response, Page, Browser

from .base_extractor import BaseExtractor, ParseError, ValidationError
from .validators import (
    ProviderData, LocationInfo, LocationSummary, 
    ExtractionStatistics, ExtractionResult,
    CarrierStatusInfo, ProviderMetadata,
    validate_extraction_data
)


class SmartsheetExtractor(BaseExtractor):
    """Production-ready Smartsheet data extractor"""
    
    def __init__(self, config: Dict[str, Any], browser: Browser):
        super().__init__(config, browser)
        
        # Status mapping
        self.status_mapping = {
            'x': 'in_network',
            'n': 'out_of_network',
            'f': 'honor_in_network_fees',
            's': 'processing',
            'p': 'processing',
            'o': 'other',
            '': 'processing',
            None: 'processing'
        }
        
        # Known carriers list (should be loaded from database in production)
        self.known_carriers = config.get('known_carriers', [
            'Aetna', 'Ameritas', 'Anthem', 'BCBS', 'Blue Cross', 'Blue Shield',
            'Careington', 'Cigna', 'Delta Dental', 'Dental Select', 'DentaQuest',
            'Dentist Direct', 'DHA', 'Diversified', 'DMBA', 'EMI', 'GEHA',
            'Guardian', 'Humana', 'Liberty', 'MCNA', 'Medicaid', 'Medicare',
            'MetLife', 'PEHP', 'Premier Access', 'Principal', 'Regence',
            'Samera', 'Select Health', 'SelectHealth', 'TDA', 'UCCI', 'UHC',
            'Unicare', 'United Concordia', 'United Healthcare', 'Wellpoint'
        ])
        
        # Non-carrier column keywords
        self.non_carrier_keywords = config.get('non_carrier_keywords', [
            'row_id', 'Providers', 'Office_Legal_Name', 'NPI_Type_1',
            'Hire Date', 'Paperwork received date', 'Submission Date',
            'Percentage', 'Degree', 'Sent Date', 'Processing Date',
            'Active Date', 'Acitve Date', 'Turn Around', 'Processing Time',
            'Comments', 'Notes', 'Status Date', 'Effective Date', 'TAT',
            'Days', 'Time', 'Date', 'Notes'
        ])
    
    async def is_target_response(self, response: Response) -> bool:
        """Check if response contains Smartsheet grid data"""
        try:
            if "smartsheet.com/w/rest/sheets/" in response.url and "columns" in response.url:
                # This is likely the column definition request
                return True

            if "smartsheet.com/w/rest/sheets/" in response.url and "rows" in response.url:
                # This is the row data request
                return True
            
            # Fallback for other data-loading mechanisms
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                try:
                    data = await response.json()
                    if isinstance(data, list) and all('columnId' in item for item in data):
                        return True # Likely column data
                    if 'rows' in data and 'columns' in data:
                        return True # Likely sheet data
                except Exception:
                    pass # Not a valid JSON response

            return False
        except Exception as e:
            self.logger.debug(f"Error checking response: {e}")
            return False
    
    async def wait_for_content(self, page: Page):
        """Wait for Smartsheet content to load"""
        try:
            # Wait for Smartsheet grid to be present
            await page.wait_for_selector('[id*="grid"]', timeout=10000)
            # Remove unnecessary hard wait - data is captured via response interception
        except Exception as e:
            self.logger.warning(f"Content wait timeout: {e}")
            # Continue anyway as data might be loaded via JavaScript
    
    async def parse_response(self, response_data: str) -> Dict[str, Any]:
        """Parse Smartsheet JSON response."""
        try:
            data = json.loads(response_data)
            
            # This assumes the response is for the entire sheet, including columns and rows
            columns_data = data.get('columns', [])
            rows_data = data.get('rows', [])

            if not columns_data or not rows_data:
                raise ParseError("Missing 'columns' or 'rows' in the JSON response.")

            # Create a column map for easy lookup
            column_map = {col['id']: col['title'] for col in columns_data}
            
            # Identify carrier columns
            carrier_columns = self._identify_carrier_columns(column_map)
            if not carrier_columns:
                raise ParseError("No carrier columns identified from the new data structure.")
            
            self.logger.info(f"Found {len(column_map)} columns, {len(carrier_columns)} carriers from JSON response.")

            # Process rows to extract providers
            providers, locations = self._parse_rows_from_json(rows_data, column_map, carrier_columns)
            
            # Calculate statistics
            statistics = self._calculate_statistics(providers, locations)
            
            return {
                'providers': providers,
                'locations': locations,
                'statistics': statistics,
                'metadata': {
                    'total_columns': len(column_map),
                    'carrier_columns': len(carrier_columns),
                    'total_rows': len(rows_data)
                }
            }
            
        except json.JSONDecodeError:
            self.logger.error("Failed to decode JSON from response.")
            raise ParseError("Invalid JSON in response.")
        except ParseError:
            raise
        except Exception as e:
            self.logger.exception("Unexpected parsing error with new JSON structure.")
            raise ParseError(f"Failed to parse JSON response: {e}")

    def _parse_rows_from_json(self, rows: List[Dict], column_map: Dict[int, str], carrier_columns: List[str]) -> Tuple[List[Dict], List[Dict]]:
        """Parse providers and locations from JSON rows"""
        
        providers = []
        locations = []
        location_stats = defaultdict(lambda: {'active': 0, 'dormant': 0})
        
        current_location = None
        current_location_id = None
        is_dormant_section = False
        state = self.extraction_id.split('_')[0] if self.extraction_id else 'unknown'
        
        # Create a reverse map for column titles to IDs for easier lookup
        title_to_id = {v: k for k, v in column_map.items()}

        for row in rows:
            row_id = row['id']
            
            # Create a dictionary of cell values for the current row
            row_data = {column_map[cell['columnId']]: cell.get('value', '') for cell in row.get('cells', [])}
            
            provider_text = row_data.get('Providers', '').strip()

            if not provider_text:
                continue

            # Check for location header
            location_match = re.match(r'^([A-Z][A-Z\s]+?)(?:\s+(\d{2}-\d{7}))?$', provider_text)
            if location_match:
                if current_location:
                    self._add_location_summary(locations, current_location, current_location_id, location_stats[current_location], state)
                
                current_location = location_match.group(1).strip()
                current_location_id = location_match.group(2) or ''
                is_dormant_section = False
                self.logger.info(f"Found location: {current_location} {current_location_id}")
                continue

            if 'dormant' in provider_text.lower() and 'provider' in provider_text.lower():
                is_dormant_section = True
                self.logger.info(f"Entering dormant section at {current_location}")
                continue

            provider_match = re.match(r'^(.+?)\s+(\d{1,3}%)$', provider_text)
            if provider_match and current_location:
                provider_name = provider_match.group(1).strip()
                percentage = provider_match.group(2)
                
                if any(skip in provider_name.lower() for skip in ['total', 'average', 'count', 'summary']):
                    continue
                
                try:
                    provider_data = self._build_provider_data(
                        provider_name, percentage, current_location,
                        current_location_id, is_dormant_section,
                        row_data, carrier_columns, state, row_id
                    )
                    
                    providers.append(provider_data)
                    
                    if is_dormant_section:
                        location_stats[current_location]['dormant'] += 1
                    else:
                        location_stats[current_location]['active'] += 1
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse provider at row {row_id}: {e}")
        
        if current_location:
            self._add_location_summary(locations, current_location, current_location_id, location_stats[current_location], state)
        
        self.logger.info(f"Parsed {len(providers)} providers across {len(locations)} locations from JSON.")
        return providers, locations

    def _identify_carrier_columns(self, columns: Dict[int, str]) -> List[str]:
        # This method should still work as it operates on a map of column names
        return super()._identify_carrier_columns(columns)

    
    def _extract_columns(self, js_content: str) -> Dict[int, str]:
        """Extract column definitions by parsing JSON from JS content"""
        columns = {}
        
        try:
            # Find the start of the main data object
            match = re.search(r'var jsdInitialData\s*=\s*({.+});', js_content, re.DOTALL)
            if not match:
                self.logger.warning("Could not find 'jsdInitialData' object in the response.")
                return {}

            json_data_str = match.group(1)
            
            # Clean up the string for JSON parsing
            # This is a simplified approach; a more robust solution might be needed
            # if the object contains complex JS constructs.
            json_data_str = re.sub(r"new Date\((\d+)\)", r"\1", json_data_str)

            try:
                data = json.loads(json_data_str)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to decode JSON from jsdInitialData: {e}")
                # Log a snippet on error for debugging
                self.logger.debug(f"JSON Snippet (first 500 chars): {json_data_str[:500]}")
                return {}

            # Navigate the object to find columns
            # This path may need adjustment based on the actual object structure
            column_defs = data.get('sheet', {}).get('columns', [])
            
            if not column_defs:
                self.logger.warning("No column definitions found in parsed JSON data.")
                return {}

            for col in column_defs:
                if 'id' in col and 'title' in col:
                    columns[int(col['id'])] = col['title']
            
            self.logger.info(f"Successfully extracted {len(columns)} columns from JSON data.")
            return columns

        except Exception as e:
            self.logger.error(f"An unexpected error occurred during column extraction: {e}")
            return {}
    
    def _extract_cells(self, js_content: str) -> List[Dict[str, Any]]:
        """Extract cell data with improved parsing"""
        cells = []
        
        try:
            # Find all data blocks
            data_blocks = re.findall(
                r"jsdSchema\.ajaxMegaBulkRecordInsert\([^;]+;",
                js_content,
                re.DOTALL
            )
            
            for block in data_blocks:
                if 'TABLE_INDEX_GRIDDATA' not in block:
                    continue
                
                # Updated regex to handle escaped quotes and special characters
                cell_pattern = r"10,\d+,(\d+),(\d+),[^,]+,[^,]+,[^,]+,'[^']*',\d+,'([^'\\]*(?:\\.[^'\\]*)*)'"
                cell_matches = re.findall(cell_pattern, block)
                
                for row_id, col_id, value in cell_matches:
                    # Unescape values
                    value = value.replace("\\'", "'").replace("\\\\", "\\")
                    value = value.replace('%25', '%').replace('\\r\\n', '\n')
                    
                    cells.append({
                        'row_id': int(row_id),
                        'col_id': int(col_id),
                        'value': value.strip()
                    })
            
            # Sort by row_id for sequential processing
            cells.sort(key=lambda x: x['row_id'])
            return cells
            
        except Exception as e:
            self.logger.error(f"Cell extraction failed: {e}")
            return cells
    
    def _identify_carrier_columns(self, columns: Dict[int, str]) -> List[str]:
        """Identify carrier columns with improved heuristics"""
        carrier_columns = []
        
        for col_name in columns.values():
            if not col_name or col_name.strip() in ['', ' ', 'grid', 'gridRow']:
                continue
            
            # Skip file extensions
            if any(ext in col_name.lower() for ext in ['.pdf', '.jpg', '.png', '.doc']):
                continue
            
            # Skip non-carrier keywords
            is_non_carrier = any(
                keyword.lower() in col_name.lower() 
                for keyword in self.non_carrier_keywords
            )
            if is_non_carrier:
                continue
            
            # Skip confirmation messages
            skip_phrases = ['confirmed', 'welcome letter', 'sent provider', 'effective']
            if any(phrase in col_name.lower() for phrase in skip_phrases):
                continue
            
            # Check for known carriers
            is_known_carrier = any(
                carrier.lower() in col_name.lower() 
                for carrier in self.known_carriers
            )
            
            # Check for plan type indicators
            plan_indicators = ['PPO', 'HMO', 'EPO', 'Classic', 'Prime', 
                             'Advantage', 'Fundamental', 'Platinum', 'Gold', 'Silver']
            has_plan_indicator = any(term in col_name for term in plan_indicators)
            
            if is_known_carrier or has_plan_indicator:
                carrier_columns.append(col_name)
        
        return carrier_columns
    
    def _parse_with_location_tracking(
        self, 
        cells: List[Dict[str, Any]], 
        columns: Dict[int, str],
        carrier_columns: List[str]
    ) -> Tuple[List[Dict], List[Dict]]:
        """Parse providers with location context tracking"""
        
        # Organize cells by row
        rows_data = defaultdict(dict)
        for cell in cells:
            col_name = columns.get(cell['col_id'], '')
            if col_name:
                rows_data[cell['row_id']][col_name] = cell['value']
        
        providers = []
        locations = []
        location_stats = defaultdict(lambda: {'active': 0, 'dormant': 0})
        
        current_location = None
        current_location_id = None
        is_dormant_section = False
        state = self.extraction_id.split('_')[0] if self.extraction_id else 'unknown'
        
        for row_id in sorted(rows_data.keys()):
            row_data = rows_data[row_id]
            provider_text = row_data.get('Providers', '').strip()
            
            if not provider_text:
                continue
            
            # Check for location header
            location_match = re.match(r'^([A-Z][A-Z\s]+?)(?:\s+(\d{2}-\d{7}))?$', provider_text)
            if location_match:
                # Save previous location
                if current_location:
                    self._add_location_summary(
                        locations, current_location, current_location_id,
                        location_stats[current_location], state
                    )
                
                current_location = location_match.group(1).strip()
                current_location_id = location_match.group(2) or ''
                is_dormant_section = False
                self.logger.info(f"Found location: {current_location} {current_location_id}")
                continue
            
            # Check for dormant section
            if 'dormant' in provider_text.lower() and 'provider' in provider_text.lower():
                is_dormant_section = True
                self.logger.info(f"Entering dormant section at {current_location}")
                continue
            
            # Parse provider
            provider_match = re.match(r'^(.+?)\s+(\d{1,3}%)$', provider_text)
            if provider_match and current_location:
                provider_name = provider_match.group(1).strip()
                percentage = provider_match.group(2)
                
                # Skip headers/summaries
                if any(skip in provider_name.lower() for skip in ['total', 'average', 'count', 'summary']):
                    continue
                
                # Build provider data
                try:
                    provider_data = self._build_provider_data(
                        provider_name, percentage, current_location,
                        current_location_id, is_dormant_section,
                        row_data, carrier_columns, state, row_id
                    )
                    
                    providers.append(provider_data)
                    
                    # Update location stats
                    if is_dormant_section:
                        location_stats[current_location]['dormant'] += 1
                    else:
                        location_stats[current_location]['active'] += 1
                        
                except Exception as e:
                    self.logger.warning(f"Failed to parse provider at row {row_id}: {e}")
        
        # Add final location
        if current_location:
            self._add_location_summary(
                locations, current_location, current_location_id,
                location_stats[current_location], state
            )
        
        self.logger.info(f"Parsed {len(providers)} providers across {len(locations)} locations")
        return providers, locations
    
    def _build_provider_data(
        self, provider_name: str, percentage: str,
        location_name: str, location_id: str,
        is_dormant: bool, row_data: Dict[str, str],
        carrier_columns: List[str], state: str,
        row_id: int
    ) -> Dict[str, Any]:
        """Build validated provider data"""
        
        # Build carrier statuses
        carrier_statuses = []
        for carrier in carrier_columns:
            status_code = row_data.get(carrier, '').lower().strip()
            status_desc = self.status_mapping.get(status_code, 'processing')
            
            carrier_statuses.append({
                'carrier': carrier,
                'status_code': status_code or '',
                'status_description': status_desc
            })
        
        # Build location info
        location_info = {
            'name': location_name,
            'location_id': location_id,
            'full_name': f"{location_name} {location_id}".strip(),
            'state': state,
            'is_active': True
        }
        
        # Build metadata
        metadata = {
            'hire_date': row_data.get('Hire Date', '').strip(),
            'submission_date': row_data.get('Submission Date', '').strip(),
            'effective_date': row_data.get('Effective Date', '').strip(),
            'row_id': row_id
        }
        
        return {
            'provider_name': provider_name,
            'percentage': percentage,
            'location': location_info,
            'is_dormant': is_dormant,
            'carrier_statuses': carrier_statuses,
            'metadata': metadata
        }
    
    def _add_location_summary(
        self, locations: List[Dict], name: str,
        location_id: str, stats: Dict[str, int], state: str
    ):
        """Add location summary with validation"""
        locations.append({
            'name': name,
            'location_id': location_id,
            'full_name': f"{name} {location_id}".strip(),
            'active_providers': stats['active'],
            'dormant_providers': stats['dormant'],
            'total_providers': stats['active'] + stats['dormant']
        })
    
    def _calculate_statistics(
        self, providers: List[Dict], locations: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate extraction statistics"""
        
        # Group by provider name
        provider_locations = defaultdict(list)
        for p in providers:
            provider_locations[p['provider_name']].append(
                p['location']['full_name']
            )
        
        # Count multi-location providers
        multi_location = sum(
            1 for locs in provider_locations.values() 
            if len(locs) > 1
        )
        
        # Count status variations
        variations = self._count_status_variations(providers)
        
        return {
            'total_provider_instances': len(providers),
            'unique_providers': len(provider_locations),
            'total_locations': len(locations),
            'multi_location_providers': multi_location,
            'carrier_status_variations': variations,
            'active_providers': sum(1 for p in providers if not p['is_dormant']),
            'dormant_providers': sum(1 for p in providers if p['is_dormant'])
        }
    
    def _count_status_variations(self, providers: List[Dict]) -> int:
        """Count carrier status variations across locations"""
        provider_carrier_status = defaultdict(lambda: defaultdict(set))
        
        for p in providers:
            name = p['provider_name']
            location = p['location']['full_name']
            
            for cs in p['carrier_statuses']:
                carrier = cs['carrier']
                status = cs['status_code']
                provider_carrier_status[name][carrier].add((location, status))
        
        # Count variations
        variations = 0
        for provider, carriers in provider_carrier_status.items():
            for carrier, location_statuses in carriers.items():
                unique_statuses = set(status for _, status in location_statuses)
                if len(unique_statuses) > 1:
                    variations += 1
        
        return variations
    
    async def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate extracted data using Pydantic models"""
        try:
            # Add required fields for validation
            validation_data = {
                'state': self.extraction_id.split('_')[0] if self.extraction_id else 'unknown',
                'extraction_date': datetime.now(timezone.utc),
                'url': 'https://smartsheet.com',  # Will be replaced with actual URL
                'extraction_id': self.extraction_id or 'unknown',
                'duration_seconds': 1.0,  # Will be replaced with actual duration
                **data
            }
            
            # Validate using Pydantic
            result = validate_extraction_data(validation_data)
            
            self.logger.info(
                f"Validation passed: {result.statistics.unique_providers} providers, "
                f"{result.statistics.total_locations} locations"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return False