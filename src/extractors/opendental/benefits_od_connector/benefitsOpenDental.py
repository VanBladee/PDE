from typing import TypedDict, Any, Optional, Tuple, Dict, List
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
from datetime import datetime, timedelta
import requests
import pymongo
import base64
import re
import os

from backend.database.dbservice_core import get_database_service

def log(message: str) -> None:
    """Log a message without timestamp"""
    print(message)

class OpenDentalPatient(TypedDict):
    patNum: str
    firstName: str
    lastName: str
    dateOfBirth: str
    groupName: str
    groupNumber: str
    insuranceName: str
    relationshipToSubscriber: str
    subscriberFirstName: str
    subscriberLastName: str
    subscriberID: str
    locationId: str
    patientAddress: str

class Result:
    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self):
        if self.success:
            return {"ok": True, "value": self.data}
        return {"ok": False, "error": self.error}

def Ok(data): return Result(True, data).to_dict()
def Err(error): return Result(False, error=error).to_dict()

class ProcedureNameMapper:
    def __init__(self, pms_code_groups: Dict[str, Any] = None, pms_procedure_aliases: Dict[str, List[str]] = None):
        """
        Initializes the mapper.
        pms_code_groups: Expected to be the codeGroups from pmsData, mapping standard names to numbers.
        pms_procedure_aliases: Expected to be like {"Standard Name": ["alias1", "alias2"]}
        """
        self.mappings = {}  # StandardName -> [list of variations including standard name lowercased]
        self.variation_to_standard = {} # variation_lowercase -> StandardName

        if pms_procedure_aliases:
            for standard_name, variations in pms_procedure_aliases.items():
                self.mappings[standard_name] = [v.lower().strip() for v in variations]
                self.mappings[standard_name].append(standard_name.lower().strip()) # Ensure standard name itself is a variation
                for variation in variations:
                    self.variation_to_standard[variation.lower().strip()] = standard_name
                self.variation_to_standard[standard_name.lower().strip()] = standard_name
        
        # Ensure all known standard names from code_groups are in the mapper,
        # even if they don't have explicit aliases. This makes them findable.
        if pms_code_groups:
            for standard_name_from_codegroup in pms_code_groups.keys():
                if standard_name_from_codegroup not in self.mappings:
                    self.mappings[standard_name_from_codegroup] = [standard_name_from_codegroup.lower().strip()]
                    self.variation_to_standard[standard_name_from_codegroup.lower().strip()] = standard_name_from_codegroup
                elif standard_name_from_codegroup.lower().strip() not in self.mappings[standard_name_from_codegroup]:
                    # If it exists from aliases, ensure the direct lowercase standard name is also there
                    self.mappings[standard_name_from_codegroup].append(standard_name_from_codegroup.lower().strip())
                    self.variation_to_standard[standard_name_from_codegroup.lower().strip()] = standard_name_from_codegroup

    def get_standard_name(self, variation: str) -> str:
        """Get standardized name from a variation"""
        normalized = variation.strip().lower()
        # Return the standard name if found, otherwise return the original variation (uppercased by convention)
        return self.variation_to_standard.get(normalized, variation.strip().upper())
    
    def get_variations(self, standard_name: str) -> list:
        """Get all variations for a standardized name"""
        return self.mappings.get(standard_name, [])
    
    def add_mapping(self, variation: str, standard_name: str):
        """Add a new mapping in both directions. Used primarily if building dynamically post-init."""
        normalized_variation = variation.strip().lower()
        if standard_name not in self.mappings:
            self.mappings[standard_name] = []
        if normalized_variation not in self.mappings[standard_name]:
            self.mappings[standard_name].append(normalized_variation)
        self.variation_to_standard[normalized_variation] = standard_name
        # Ensure the standard name itself maps to itself
        if standard_name.lower().strip() not in self.variation_to_standard:
            self.variation_to_standard[standard_name.lower().strip()] = standard_name
            if standard_name not in self.mappings:
                 self.mappings[standard_name] = [standard_name.lower().strip()]
            elif standard_name.lower().strip() not in self.mappings[standard_name]:
                 self.mappings[standard_name].append(standard_name.lower().strip())

    def get_all_standard_names(self) -> list:
        """Get list of all standardized names"""
        return list(self.mappings.keys())

class OpenDentalAPI:
    PLAN_TYPE_VARIANTS = {
        'p': ['PPO', 'PPO Percentage', 'ppo', 'percentage'],
        'f': ['Flat Copay', 'copay'],
        'c': ['Capitation', 'cap'],
        '': ['']
    }
    PLAN_TYPES = {variant: plan_type for plan_type, variants in PLAN_TYPE_VARIANTS.items()
                  for variant in variants}
    
    RELATIONSHIP_VARIANTS = {
        'Self': ['', 'self', 'sub', 'subscriber', 'member', 'primary'],
        'Spouse': ['spouse', 'sp', 'wife', 'husband'],
        'Child': ['child', 'ch', 'son', 'daughter'],
        'Employee': ['employee', 'emp'],
        'HandicapDep': ['handicapdep', 'handicap dependent', 'handicapped dependent'],
        'SignifOther': ['signifother', 'significant other', 'other'],
        'InjuredPlantiff': ['injuredplantiff', 'injured plantiff'],
        'LifePartner': ['lifepartner', 'life partner', 'partner', 'domestic partner'],
        'Dependent': ['dependent', 'dep']
    }
    RELATIONSHIPS = {variant: rel_type for rel_type, variants in RELATIONSHIP_VARIANTS.items()
                     for variant in variants}

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return OpenDentalAPI._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    @staticmethod
    def _build_regex_for_name_part(query_part: str) -> str:
        """
        Builds a regex for a single name part (e.g., first name or last name query)
        with enhanced flexibility for name variations.
        """
        if not query_part or not query_part.strip():
            return r".*"  # Match anything if no valid query

        query_part_normalized = query_part.lower().strip()
        
        # Split by sequences of hyphens, spaces, or apostrophes to get name tokens
        name_tokens = re.split(r'[-\s\']+', query_part_normalized)
        name_tokens = [token for token in name_tokens if token]  # Remove empty strings
        
        if not name_tokens:
            return r".*"
            
        regex_parts = []
        
        for token in name_tokens:
            escaped_token = re.escape(token)
            
            if len(token) == 1:  # Initial
                regex_parts.append(fr'(?:\b{escaped_token}(?:\.|[a-z]*)\b)')
            elif len(token) == 2:  # Very short name or partial
                regex_parts.append(fr'(?:\b{escaped_token}[a-z]{{0,3}}\b)')
            else:  # Longer name part
                min_prefix_len = min(2, len(token) - 1)
                patterns = []
                patterns.append(fr'\b{escaped_token}[a-z]*\b')
                if len(token) >= 4:
                    first_letter = escaped_token[0]
                    last_part = escaped_token[-2:] if len(token) > 4 else escaped_token[-1]
                    middle_len = len(token) - len(last_part) - 1
                    patterns.append(fr'\b{first_letter}[a-z]{{{max(1, middle_len-1)},{middle_len+1}}}' + 
                                re.escape(last_part) + r'[a-z]*\b')
                for prefix_len in range(len(token)-1, min_prefix_len-1, -1):
                    prefix = token[:prefix_len]
                    escaped_prefix = re.escape(prefix)
                    patterns.append(fr'\b{escaped_prefix}[a-z]*\b')
                regex_parts.append(f'(?:{"|".join(patterns)})')
        
        final_regex = r'(?:.*?| )' .join(regex_parts)
        return final_regex

    def _find_best_name_match(self, first_name_query: str, patient_list: List[Dict], log_prefix: str) -> Optional[Dict]:
        """ 
        Finds the best matching patient from a list based on first name similarity.
        Returns the best matching patient dict or None.
        """
        if not first_name_query or not patient_list:
            return None

        best_matches = []
        first_name_query_lower = first_name_query.lower().strip()

        for patient_record in patient_list:
            entity_first_name_raw = patient_record.get('FName', '')
            if not entity_first_name_raw: 
                continue
            
            entity_first_name_lower = entity_first_name_raw.lower().strip()
            score = 0.0

            # Check for exact match first (highest priority)
            if entity_first_name_lower == first_name_query_lower:
                score = 1.0  # Perfect match
            else:
                # Try regex match (more flexible for initials, etc.)
                fn_regex = self._build_regex_for_name_part(first_name_query_lower) 
                if re.search(fn_regex, entity_first_name_lower):
                    # Prioritize regex matches, especially if query is short (like an initial)
                    score = 0.85 
                    if len(first_name_query_lower) <= 2:
                        score = 0.88  # Lower than exact match but still high for initials
                
                # If regex didn't give a high score, or for general comparison, use other heuristics
                if score < 0.85: 
                    if entity_first_name_lower.startswith(first_name_query_lower):
                        # Prefix match - score based on how much of the full name is matched
                        match_ratio = len(first_name_query_lower) / len(entity_first_name_lower)
                        # For "Mo" vs "Mosalina": match_ratio = 2/8 = 0.25
                        # For "Mo" vs "Mo": would be exact match (already handled above)
                        score = max(score, 0.8 + (match_ratio * 0.15))  # 0.8 to 0.95 range
                    elif first_name_query_lower.startswith(entity_first_name_lower):
                        score = max(score, 0.75)
                    elif entity_first_name_lower in first_name_query_lower:
                        score = max(score, 0.7)
                    elif first_name_query_lower in entity_first_name_lower:
                        score = max(score, 0.6)
            
            # Levenshtein distance for closer matches if other heuristics are weak
            if score < 0.75: # Only use Levenshtein if not a strong match by other means
                distance = self._levenshtein_distance(entity_first_name_lower, first_name_query_lower)
                max_len = max(len(entity_first_name_lower), len(first_name_query_lower))
                if max_len > 0:
                    similarity = 1.0 - (distance / max_len)
                    if similarity >= 0.6: # Levenshtein threshold
                        # Scale Levenshtein to be comparable but generally lower than direct heuristics
                        score = max(score, similarity * 0.65) 
            
            if score > 0.6: # Minimum score threshold to be considered a potential match
                best_matches.append({"entity": patient_record, "score": score, "matched_fname": entity_first_name_raw})
                log(f"{log_prefix} Potential FName match: Query '{first_name_query}' vs Record '{entity_first_name_raw}' (Score: {score:.2f})")

        if not best_matches:
            return None

        best_matches = sorted(best_matches, key=lambda x: x["score"], reverse=True)
        
        # Logic to select the best candidate
        top_match = best_matches[0]
        log(f"{log_prefix} Top FName match: '{top_match['matched_fname']}' with score {top_match['score']:.2f} for query '{first_name_query}'")

        if top_match["score"] >= 0.8: # High confidence threshold
            if len(best_matches) > 1 and top_match["score"] - best_matches[1]["score"] < 0.1: # Check for ambiguity
                # Only consider it ambiguous if both are NOT exact matches
                # If top match is exact (1.0), it should win even if second is close
                if top_match["score"] < 0.99:
                    log(f"{log_prefix} Ambiguous FName match. Top: {top_match['score']:.2f}, Next: {best_matches[1]['score']:.2f}. Not selecting.")
                    return None
            log(f"{log_prefix} Selected FName match (high confidence): {top_match['entity'].get('FName')} {top_match['entity'].get('LName')}")
            return top_match["entity"]
        elif top_match["score"] >= 0.65: # Medium confidence, accept if it's the only one reasonable one
            log(f"{log_prefix} Selected FName match (medium confidence): {top_match['entity'].get('FName')} {top_match['entity'].get('LName')}")
            return top_match["entity"]
        
        log(f"{log_prefix} No sufficiently confident FName match found for query '{first_name_query}'.")
        return None

    @staticmethod
    def normalize_carrier_name(name: str) -> str:
        """Normalizes carrier names using simple rules that work for any company name."""
        if not name: return ""
        normalized = name.lower()
        normalized = re.sub(r'[^a-z0-9]', ' ', normalized)
        normalized = ' '.join(normalized.split())
        common_words = ['insurance', 'ins', 'company', 'co', 'corp', 'corporation', 'incorporated', 'inc',
                        'dental', 'health', 'life', 'of', 'the', 'and', 'group', 'services', 'limited', 'ltd']
        pattern = r'\b(' + '|'.join(common_words) + r')\b'
        normalized = re.sub(pattern, '', normalized)
        return ' '.join(normalized.split())

    def __init__(self, base_url=None, auth_token=None, pms_data=None, locationId=None):        
        if not base_url: raise ValueError("OpenDental API URL not found in location settings")
        if not auth_token: raise ValueError("OpenDental auth token not found in location settings")
        if not base_url.startswith(('http://', 'https://')): base_url = f"https://{base_url}"
            
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.headers = {'Authorization': self.auth_token, 'Content-Type': 'application/json'}
        self.pms_data = pms_data or {}
        self.locationId = locationId
        self.api_responses = [] # To store API call logs
        
        # Initialize Database Service
        self.db_service = get_database_service()

        # Initialize procedure name mapper early, it will be populated by _initialize_mappings
        self.procedure_mapper = ProcedureNameMapper() 
        # Initialize mapping from pms data
        self._initialize_mappings()

    def _initialize_mappings(self):
        """Initialize mappings from PMS data"""
        pms_data = self.pms_data
        
        # Map providers
        self.providers = {}
        for provider in pms_data.get('providerInfo', {}).values():
            if provider.get('name') and provider.get('providerNpi'):
                self.providers[provider['name']] = {
                    'npi': provider['providerNpi'],
                    'feeSched': provider.get('FeeSched'),
                    'priProv': provider.get('priProv')
                }

        # Map carriers
        self.carriers = {}
        self._normalized_carriers = {}
        
        for carrier_name, carrier_id in pms_data.get('carriers', {}).items():
            # Store original mapping
            self.carriers[carrier_name] = carrier_id
            
            # Store normalized mapping
            norm_name = self.normalize_carrier_name(carrier_name)
            if norm_name:  # Only store if normalized name isn't empty
                self._normalized_carriers[norm_name] = carrier_id

        # Map code groups
        self.code_groups = {}
        for group_name, group_num in pms_data.get('codeGroups', {}).items():
            self.code_groups[group_name] = group_num

        # Map coverage categories
        self.cov_cats = {}
        for cat_name, cat_num in pms_data.get('covCats', {}).items():
            self.cov_cats[cat_name] = cat_num

        # Initialize ProcedureNameMapper with data from pmsData
        pms_code_groups = pms_data.get('codeGroups', {})
        pms_procedure_aliases = pms_data.get('procedureAliases', {}) # New field from pmsData
        self.procedure_mapper = ProcedureNameMapper(pms_code_groups, pms_procedure_aliases)

    def make_request(self, endpoint: str, method: str = 'GET', data: dict = None) -> dict:
        """Makes a request to the OpenDental API"""
        full_url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        log(f"{method} request to {endpoint}")
        
        try:
            timeout = 60 if endpoint == 'documents/Upload' else 30

            if method == 'GET':
                response = requests.get(full_url, headers=self.headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(full_url, headers=self.headers, json=data, timeout=timeout)
            elif method == 'PUT':
                response = requests.put(full_url, headers=self.headers, json=data, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(full_url, headers=self.headers, timeout=timeout)
                # For DELETE requests, if successful with no content, return empty dict
                if response.status_code == 204:
                    log(f"Completed {method} request to {endpoint} - Status: 204 No Content")
                    # Optionally log DELETE calls if needed, similar to POST/PUT below
                    return {}
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response_json = None
            if response.text.strip():
                try:
                    response_json = response.json()
                except ValueError: # Handle cases where response is not valid JSON
                    response_json = {"raw_response": response.text}

            # Log POST and PUT requests
            if method in ['POST', 'PUT']:
                self.api_responses.append({
                    'timestamp': datetime.now().isoformat(),
                    'method': method,
                    'endpoint': endpoint,
                    'request_data': data,
                    'status_code': response.status_code,
                    'response_json': response_json
                })

            if not response.ok:
                log(f"Failed {method} request to {endpoint} - Status: {response.status_code}")
                raise Exception(f"OpenDental API error: {response.status_code} - {response.text}")

            # Try to parse as JSON, but handle case where response might be empty
            response_size = len(response.text) if response.text else 0
            log(f"Completed {method} request to {endpoint} - Status: {response.status_code}, Size: {response_size} bytes")
            
            return response_json if response_json is not None else {}
        except Exception as error:
            log(f"Error in {method} request to {endpoint}: {error}")
            raise

    def get_api_responses(self) -> List[Dict]:
        """Returns a copy of the collected API responses."""
        return self.api_responses.copy()

    def clear_api_responses(self) -> None:
        """Clears the collected API responses."""
        self.api_responses = []

    def get_existing_benefits(self, plan_num: int) -> list:
        """
        Fetches all existing benefits for a plan.
        Returns empty list if no benefits exist or an error occurs.
        """
        try:
            log(f"Fetching existing benefits for plan {plan_num}")
            benefits = self.make_request(f'/benefits?PlanNum={plan_num}')
            log(f"Found {len(benefits)} existing benefits for plan {plan_num}")
            return benefits
        except Exception as error:
            log(f"Error fetching existing benefits: {error}")
            return []

    def get_existing_patplans(self, pat_num: int) -> list:
        """
        Fetches all existing PatPlans for a patient.
        Returns empty list if no PatPlans exist or an error occurs.
        """
        try:
            log(f"Fetching existing PatPlans for patient {pat_num}")
            patplans = self.make_request(f'/patplans?PatNum={pat_num}')
            log(f"Found {len(patplans)} existing PatPlans for patient {pat_num}")
            return patplans
        except Exception as error:
            log(f"Error fetching existing PatPlans: {error}")
            return []
            
    def has_existing_patplan(self, pat_num: int, ins_sub_num: int) -> bool:
        """
        Checks if a PatPlan already exists for a patient with a specific InsSubNum.
        Returns True if it exists, False otherwise.
        """
        try:
            log(f"Checking for existing PatPlan for patient {pat_num} with InsSubNum {ins_sub_num}")
            patplans = self.get_existing_patplans(pat_num)
            for patplan in patplans:
                if patplan.get('InsSubNum') == ins_sub_num:
                    log(f"Found existing PatPlan for patient {pat_num} with InsSubNum {ins_sub_num}")
                    return True
            log(f"No existing PatPlan found for patient {pat_num} with InsSubNum {ins_sub_num}")
            return False
        except Exception as error:
            log(f"Error checking for existing PatPlan: {error}")
            return False

    def search_for_patient_by_name(self, last_name: str, first_name: str) -> dict:
        log(f"Searching for patient with name: {first_name} {last_name}")
        try:
            # Search by last name first
            patients_by_lname = self.make_request(f"patients/Simple?LName={last_name}&PatStatus=Patient")
            if not patients_by_lname or not isinstance(patients_by_lname, list):
                log(f"No patients found with last name '{last_name}'.")
                return {"match": None, "results": []}

            # If first name is provided, find the best match
            if first_name:
                best_match = self._find_best_name_match(first_name, patients_by_lname, f"PatientSearch:")
                if best_match:
                    log(f"Found best match for {first_name} {last_name}: PatNum {best_match.get('PatNum')}")
                    return {"match": best_match, "results": [best_match]} # Return single best match
                else:
                    log(f"No confident first name match for '{first_name}' among patients with last name '{last_name}'. Returning all results.")
                    return {"match": None, "results": patients_by_lname}
            else:
                # If no first name, return all patients with that last name
                log(f"Returning all {len(patients_by_lname)} patients with last name '{last_name}'.")
                return {"match": None, "results": patients_by_lname}

        except Exception as e:
            log(f"Error during patient search for name '{first_name} {last_name}': {str(e)}")
            return {"match": None, "results": [], "error": str(e)}

    def create_or_update_benefit(self, benefit: dict, existing_benefit: dict = None) -> bool:
        """
        Creates a new benefit or updates an existing one.
        Returns True if successful, False otherwise.
        """
        try:
            if existing_benefit:
                # Get BenefitNum from existing benefit
                benefit_num = existing_benefit['BenefitNum']
                
                log(f"Updating existing benefit {benefit_num}")
                
                # Create a copy of the existing benefit to preserve all fields
                update_benefit = existing_benefit.copy()
                
                # Update with new values from benefit
                for key, value in benefit.items():
                    update_benefit[key] = value
                
                # Ensure BenefitNum is preserved
                update_benefit['BenefitNum'] = benefit_num
                
                # Make PUT request to update benefit
                self.make_request(f'/benefits/{benefit_num}', 'PUT', update_benefit)
                log("Successfully updated benefit")
                return True
            else:
                log(f"Creating new benefit of type {benefit.get('BenefitType')}")
                # Make POST request to create new benefit
                self.make_request('/benefits', 'POST', benefit)
                log("Successfully created new benefit")
                return True
        except Exception as error:
            log(f"Error creating/updating benefit: {error}")
            return False

    def get_form_value(self, form_data: dict, *keys, default='') -> str:
        """Safely get value from nested form data"""
        for key in keys:
            if not isinstance(form_data, dict):
                return default
            form_data = form_data.get(key, {})
        
        # If the value is another dict with a 'value' key, extract that
        if isinstance(form_data, dict):
            # Handle nested value objects (used by planNotes)
            if 'value' in form_data and isinstance(form_data['value'], dict) and 'value' in form_data['value']:
                return form_data['value']['value']
            # Handle standard value objects
            return form_data.get('value', default)
        
        return form_data

    def normalize_relationship(self, relationship: str) -> str:
        """Normalize relationship value to valid OpenDental format"""
        return self.RELATIONSHIPS.get(relationship.lower().strip() if relationship else '', 'Self')
    
    def get_or_create_carrier(self, form: dict) -> int:
        """Gets existing carrier or creates new one with confidence-based matching."""
        insurance_name = self.get_form_value(form, 'insurance', 'name', default='')
        if not insurance_name: return 0
            
        normalized_input = self.normalize_carrier_name(insurance_name)
        log(f"Processing carrier: {insurance_name} (normalized name: {normalized_input})")
        
        # Try exact match
        if normalized_input in self._normalized_carriers:
            carrier_id = self._normalized_carriers[normalized_input]
            log(f"Found exact match for carrier: {carrier_id}")
            return carrier_id
            
        # Look for high-confidence partial matches
        matches = []
        for pms_name, carrier_id in self._normalized_carriers.items():
            confidence = self._calculate_match_confidence(normalized_input, pms_name)
            if confidence > 0:
                matches.append({'name': pms_name, 'id': carrier_id, 'confidence': confidence})
        
        # Sort matches by confidence
        matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Use high confidence match if available
        if matches and matches[0]['confidence'] >= 0.8:
            carrier_id = matches[0]['id']
            log(f"Found high-confidence match for carrier: {carrier_id} (confidence: {matches[0]['confidence']})")
            return carrier_id
            
        # Create new carrier
        log(f"Creating new carrier: {insurance_name}")
        carrier_response = self.make_request('/carriers', 'POST', {
            'CarrierName': insurance_name,
            'Address': self.get_form_value(form, 'insurance', 'claimsAddress', default=''),
            'Address2': self.get_form_value(form, 'insurance', 'claimsAddress2', default=''),
            'City': self.get_form_value(form, 'insurance', 'claimsCity', default=''),
            'State': self.get_form_value(form, 'insurance', 'claimsState', default=''),
            'Zip': self.get_form_value(form, 'insurance', 'claimsZip', default='00000'),
            'ElectID': self.get_form_value(form, 'insurance', 'payerId', default=''),
            'NoSendElect': 'SendElect'
        })
        
        new_carrier_num = carrier_response['CarrierNum']
        
        # Update our local mappings
        self.carriers[insurance_name] = new_carrier_num
        self._normalized_carriers[normalized_input] = new_carrier_num
        
        # Update MongoDB with the new carrier in od_live collections
        db_service = self.db_service
        
        # Get current carriers from od_live
        current_carriers = db_service.get_carriers_for_location(self.locationId)
        current_carriers[insurance_name] = new_carrier_num
        
        # Update the od_live carriers collection
        db_service.update_location_pms_data(self.locationId, {'carriers': current_carriers})
        log("Updated MongoDB od_live carriers with new carrier")
        
        # Update the local pms_data and re-initialize mappings
        self.pms_data['carriers'] = current_carriers
        self._initialize_mappings()
        
        log(f"Created new carrier: {new_carrier_num}")
        return new_carrier_num

    def _calculate_match_confidence(self, input_name: str, pms_name: str) -> float:
        """
        Calculates match confidence score between 0 and 1.
        Uses multiple matching strategies for better accuracy.
        """
        if not input_name or not pms_name:
            return 0.0
            
        # Start with base confidence
        confidence = 0.0
        
        # Exact match check
        if input_name == pms_name:
            return 1.0
            
        # Contained string check
        if input_name in pms_name:
            confidence = max(confidence, 0.9)
        elif pms_name in input_name:
            confidence = max(confidence, 0.85)
            
        # Word matching
        input_words = set(input_name.split())
        pms_words = set(pms_name.split())
        
        if input_words and pms_words:
            common_words = input_words & pms_words
            total_words = input_words | pms_words
            if total_words:
                word_confidence = len(common_words) / len(total_words)
                confidence = max(confidence, word_confidence)
                
        # Character sequence matching
        total_chars = max(len(input_name), len(pms_name))
        if total_chars > 0:
            matching_chars = sum(a == b for a, b in zip(input_name.ljust(total_chars), pms_name.ljust(total_chars)))
            char_confidence = matching_chars / total_chars
            confidence = max(confidence, char_confidence * 0.8)  # Weight character matching less
            
        return confidence

            
    def get_code_group_num(self, group_name: str) -> int:
        """Gets the CodeGroupNum from PMS data with normalized procedure names"""
        try:
            if not group_name:
                return 0
                
            # Get standardized name using the mapper
            standard_name = self.procedure_mapper.get_standard_name(group_name)
            
            # Get the code group number
            code_group_num = self.code_groups.get(standard_name, 0)
            
            if code_group_num == 0:
                log(f"Warning: Could not find CodeGroupNum for procedure: {group_name} (normalized: {standard_name})")
            
            return code_group_num
        except Exception as e:
            log(f"Error getting code group num for {group_name}: {e}")
            return 0

    def update_insurance_plan(self, plan_num: int, plan_data: dict) -> bool:
        """
        Updates an existing insurance plan with new data.
        Returns True if successful, False otherwise.
        
        Args:
            plan_num: The PlanNum of the plan to update
            plan_data: Dictionary containing the fields to update
        """
        try:
            log(f"Updating insurance plan {plan_num}")
            log(f"Update payload before processing: {plan_data}")

            if 'PlanType' in plan_data: 
                original_plan_type = plan_data['PlanType']
                plan_data['PlanType'] = self.PLAN_TYPES.get(plan_data['PlanType'], plan_data['PlanType'])
                log(f"Converted PlanType from '{original_plan_type}' to '{plan_data['PlanType']}'")
            
            log(f"Final update payload being sent: {plan_data}")
            
            # Make PUT request to update the insurance plan
            response = self.make_request(f'/insplans/{plan_num}', 'PUT', plan_data)
            log(f"Successfully updated insurance plan {plan_num}, Response: {response}")
            return True
        except Exception as error:
            log(f"Error updating insurance plan: {error}")
            log(f"Failed update payload was: {plan_data}")
            return False
        
    def create_patient(self, patient_data: dict, address_fields: dict, guarantor_pat_num: Optional[int] = None) -> int:
        """Helper function to create a patient, optionally linking to a family guarantor."""
        log(f"Creating patient: {patient_data.get('firstName')} {patient_data.get('lastName')}")
        
        #format patient dob to YYYY-MM-DD
        formatted_birthdate = self.format_date(patient_data['birthdate'])
        if not formatted_birthdate:
            log(f"Warning: Could not format birthdate '{patient_data['birthdate']}' for patient {patient_data.get('firstName')} {patient_data.get('lastName')}.")
            pass # Or raise ValueError("Formatted birthdate is empty, cannot proceed with patient creation.")

        # First check for existing patient
        search_response = self.make_request(
            f'/patients/Simple?LName={patient_data["lastName"]}&FName={patient_data["firstName"]}&PatStatus=Patient'
        )
        
        # If patient exists, use their PatNum
        if search_response and len(search_response) > 0:
            pat_num = search_response[0]['PatNum']
            log(f"Found existing patient with PatNum: {pat_num}")
            return pat_num
            
        patient_params = {
            'LName': patient_data['lastName'],
            'FName': patient_data['firstName'],
            # 'Birthdate': formatted_birthdate, # Use the formatted birthdate
            'Address': address_fields['Address'],
            'Address2': address_fields['Address2'],
            'City': address_fields['City'],
            'State': address_fields['State'],
            'Zip': address_fields['Zip']
        }
        
        if formatted_birthdate:
            patient_params['Birthdate'] = formatted_birthdate

        # Add Guarantor if provided, otherwise let OpenDental default to self
        if guarantor_pat_num is not None:
            patient_params['Guarantor'] = guarantor_pat_num
        
        patient_response = self.make_request('/patients', 'POST', patient_params)
        
        if not patient_response or 'PatNum' not in patient_response or patient_response['PatNum'] is None:
            error_msg = f"Error: POST /patients for {patient_data.get('firstName')} {patient_data.get('lastName')} - PatNum is missing or null. Response: {patient_response}"
            log(error_msg)
            raise Exception(error_msg)
        
        pat_num = patient_response['PatNum']
        
        if not isinstance(pat_num, int) or pat_num <= 0: # Assuming PatNum must be a positive integer
            error_msg = f"Error: POST /patients for {patient_data.get('firstName')} {patient_data.get('lastName')} - PatNum is invalid ({pat_num}). Response: {patient_response}"
            log(error_msg)
            raise Exception(error_msg)
            
        log(f"Created new patient with PatNum: {pat_num}")
        return pat_num

    def get_cov_cat_num(self, category_name: str) -> int:
        """Gets the CovCatNum from PMS data"""
        return self.cov_cats.get(category_name, 0)

    def setup_patient_benefits(self, patient_data: dict, is_dependent: bool = False) -> dict:
        """Sets up patient benefits in OpenDental"""
        try:
            log("Starting patient benefits setup")
            self.clear_api_responses() # Clear any previous API responses
            
            form = patient_data.get('form', {})
            # Basic patient setup first
            setup_result = self.setup_basic_patient(patient_data)
            if not setup_result.get('ok'):
                log(f"Basic patient setup failed: {setup_result.get('error')}")
                return setup_result
                
            self.pat_num = setup_result['value']['data']['patNum']
            self.plan_num = setup_result['value']['data']['planNum']
            self.InsSubNum = setup_result['value']['data']['InsSubNum']
            self.using_existing_plan = setup_result['value'].get('data', {}).get('using_existing_plan', False)

            log(f"Patient setup complete. Processing benefits for plan {self.plan_num}")
            
            # Check if using existing plan
            existing_benefits = []
            if self.using_existing_plan:
                existing_benefits = self.get_existing_benefits(self.plan_num)
            
            benefits_to_create = []
            self.process_benefits_dynamically(form, benefits_to_create)
            
            # Use parallel processing for benefits
            log(f"Using parallel processing for {len(benefits_to_create)} benefits")
            benefits_result = self.process_benefits_in_parallel(benefits_to_create, existing_benefits)
            
            successful_benefits = benefits_result['successful']
            updated_benefits = benefits_result['updated']
            failed_benefits = benefits_result['failed']
            skipped_updates_count = benefits_result.get('skipped', 0) # Get skipped count
            
            log(f"Benefits processing complete - Created: {successful_benefits - updated_benefits}, "
                f"Updated: {updated_benefits}, Failed: {failed_benefits}, Skipped: {skipped_updates_count}")
            
            return Ok({
                "message": "Patient setup completed successfully",
                "data": {
                    "patNum": self.pat_num,
                    "planNum": self.plan_num,
                    "InsSubNum": self.InsSubNum,
                    "benefitsCreated": successful_benefits - updated_benefits,
                    "benefitsUpdated": updated_benefits,
                    "benefitsFailed": failed_benefits,
                    "benefitsSkipped": skipped_updates_count, # Added for skipped updates
                    "benefitsAttempted": len(benefits_to_create),
                    "using_existing_plan": self.using_existing_plan,
                    "api_responses": self.get_api_responses() # Include all API responses
                }
            })
            
        except Exception as error:
            log(f"Failed to set up patient: {str(error)}")
            # Include API responses in error return if available
            error_data = {
                "error": f"Failed to set up patient: {str(error)}",
                "api_responses": self.get_api_responses() 
            }
            return Err(error_data)

    def refresh_pms_data(self) -> None:
        """Refreshes the local pmsData from od_live collections to ensure it's up-to-date."""
        log("Refreshing PMS data from od_live collections")
        db_service = self.db_service
        
        # Get PMS data from od_live collections
        self.pms_data = db_service.get_pms_data_for_location(self.locationId)
        self._initialize_mappings()
        log("PMS data refreshed from od_live collections")

    def update_pms_data_with_plan(self, plan_num: int, group_name: str, group_num: str) -> bool:
        """Updates the insurance plans in od_live collections with a new insurance plan."""
        log(f"Updating od_live collections with new plan {plan_num} for group {group_name}")
        
        db_service = self.db_service
        
        # Get existing insurance plans and add new plan
        existing_plans = db_service.get_insurance_plans_for_location(self.locationId)
        existing_plans[group_name] = {'planNum': plan_num, 'groupNum': group_num}
        
        # Update od_live collections with merged plans
        db_service.update_location_pms_data(self.locationId, {'insurancePlans': existing_plans})
        log("od_live collections update completed")
        
        # Update local instance data
        self.pms_data['insurancePlans'] = existing_plans
        log("PMS data updated with new plan")
        return True

    def format_date(self, date_str: str) -> str:
        """Formats a date string to YYYY-MM-DD if possible, otherwise returns empty string."""
        if not date_str:
            return ''

        original_date_str = str(date_str).strip()
        if not original_date_str:
            return ''

        # Normalize separators: replace / with -
        normalized_date_str = original_date_str.replace('/', '-')

        # Define common date formats to try
        # Order matters: try more specific or common US ones first
        date_formats_to_try = [
            '%Y-%m-%d',  # Standard YYYY-MM-DD
            '%m-%d-%Y',  # MM-DD-YYYY (e.g., 07-22-1990)
            '%m-%d-%y',  # MM-DD-YY (e.g., 07-22-90)
        ]

        for fmt in date_formats_to_try:
            try:
                # Attempt to parse the date string
                dt_obj = datetime.strptime(normalized_date_str, fmt)
                # If successful, format it to YYYY-MM-DD
                return dt_obj.strftime('%Y-%m-%d')
            except ValueError:
                # If parsing fails, try the next format
                continue
        
        # Attempt to parse "MM-DD" (e.g., "5-24") and assume current year
        try:
            current_year = datetime.now().year
            dt_obj_mm_dd = datetime.strptime(normalized_date_str, '%m-%d')
            # If successful, replace year with current year
            dt_obj_with_year = dt_obj_mm_dd.replace(year=current_year)
            log(f"Parsed '{original_date_str}' as MM-DD format for current year: {dt_obj_with_year.strftime('%Y-%m-%d')}")
            return dt_obj_with_year.strftime('%Y-%m-%d')
        except ValueError:
            # If MM-DD parsing also fails, then log the warning and return empty.
            pass # Proceed to the original warning log and return empty string
        
        log(f"Warning: Could not parse date string '{original_date_str}' (normalized: '{normalized_date_str}') into YYYY-MM-DD format. Returning empty string.")
        return '' # Return empty string on failure
            
    def setup_basic_patient(self, patient_data: dict) -> dict:
        log("Starting basic patient setup")
        
        # Log incoming patient_data for debugging fee schedule
        log(f"Incoming patient_data keys: {list(patient_data.keys())}")
        pms_matches_debug = patient_data.get('pms_matches', {})
        log(f"Full pms_matches content: {pms_matches_debug}")
        fee_schedule_match_debug = pms_matches_debug.get('fee_schedule_match', {})
        log(f"Fee schedule match details: {fee_schedule_match_debug}")
        
        # ---- EXTRACT CORE DATA ----
        form = patient_data.get('form', {})
        
        # User intent flags and corresponding pre-matched entity IDs
        use_existing_plan = patient_data.get('useExistingPlan', False)
        use_existing_subscriber = patient_data.get('useExistingSubscriber', False)
        use_existing_patient = patient_data.get('useExistingPatient', False)
        
        existing_plan_num = patient_data.get('existingPlanNum')
        existing_ins_sub_num = patient_data.get('existingInsSubNum')
        existing_pat_num = patient_data.get('existingPatNum')
        
        # Validate that entity IDs exist when corresponding flags are true
        if use_existing_plan and not existing_plan_num:
            log("Warning: useExistingPlan is True but no existingPlanNum provided")
            use_existing_plan = False
        
        if use_existing_subscriber and not existing_ins_sub_num:
            log("Warning: useExistingSubscriber is True but no existingInsSubNum provided")
            use_existing_subscriber = False
        
        if use_existing_patient and not existing_pat_num:
            log("Warning: useExistingPatient is True but no existingPatNum provided")
            use_existing_patient = False
        
        log(f"User intent - Use existing plan: {use_existing_plan}, subscriber: {use_existing_subscriber}, patient: {use_existing_patient}")
        
        # Extract key form values
        plan_note = self.get_form_value(form, 'insPlanNote', 'value', default='')
        group_name = self.get_form_value(form, 'planDetails', 'groupName', default='')
        group_num = self.get_form_value(form, 'planDetails', 'groupNumber', default='')
        subscriber_id = self.get_form_value(form, 'subscriber', 'subscriberID', default='')
        
        # Relationship determines if patient is the subscriber or dependent
        relationship = patient_data.get('familyRelationship') or self.get_form_value(form, 'patient', 'relationshipToSubscriber', default='Self')
        is_self_relationship = (relationship == 'Self')
        
        log(f"Relationship: {relationship}, Is Self: {is_self_relationship}")
        
        # Format dates
        effective_date = self.format_date(self.get_form_value(form, 'planDetails', 'effectiveDate', default=''))
        termination_date = self.format_date(self.get_form_value(form, 'planDetails', 'terminationDate', default=''))
        
        # Clean and format address
        zip_value = self.get_form_value(form, 'patient', 'zip', default='')
        clean_zip = ''.join(filter(str.isdigit, zip_value))[:5]
        clean_zip = clean_zip.zfill(5) if clean_zip else '00000'
        
        address_fields = {
            'Address': self.get_form_value(form, 'patient', 'address', default=''),
            'Address2': self.get_form_value(form, 'patient', 'address2', default=''),
            'City': self.get_form_value(form, 'patient', 'city', default=''),
            'State': self.get_form_value(form, 'patient', 'state', default=''),
            'Zip': clean_zip
        }
        
        for key in ['Address', 'Address2', 'City', 'State']:
            value = address_fields[key]
            value = ''.join(c for c in value if c.isalnum() or c.isspace() or c in '-#,.')
            address_fields[key] = value[:100] if value else ''
        
        # ---- GET CARRIER ----
        log("Obtaining carrier information")
        carrier_num = self.get_or_create_carrier(form)
        log(f"Carrier processing completed: CarrierNum={carrier_num}")
        
        if carrier_num == 0:
            return Err("Failed to get or create carrier")
        
        # ---- INITIALIZE ENTITY VARIABLES ----
        pat_num = None
        plan_num = None
        ins_sub_num = None
        subscriber_pat_num = None  # PatNum of the subscriber (for dependent relationships)
        
        # ---- PROCESS PLAN ----
        log("Processing insurance plan")
        
        if use_existing_plan:
            # User explicitly provided a plan ID
            plan_num = existing_plan_num
            log(f"Using user-provided plan: PlanNum={plan_num}")
        else:
            # Try to find matching plan by group info
            self.refresh_pms_data()
            matching_plan = self.find_matching_plan(group_name, group_num)
            
            if matching_plan:
                plan_num = matching_plan['planNum']
                log(f"Found matching plan: PlanNum={plan_num}")
            # Otherwise we'll create a new plan later
        
        # If plan found or provided, update it with any new info
        if plan_num:
            plan_updates = {}
            
            if plan_note:
                plan_updates['PlanNote'] = plan_note
            
            plan_type = self.get_form_value(form, 'planDetails', 'planType', default='')
            if plan_type:
                plan_updates['PlanType'] = self.PLAN_TYPES.get(plan_type, plan_type)
            
            # Check if fee schedule was selected from pms_matches
            fee_schedule_match = patient_data.get('pms_matches', {}).get('fee_schedule_match', {})
            log(f"Checking fee schedule for plan update - fee_schedule_match: {fee_schedule_match}")
            if fee_schedule_match.get('found_fee_schedule') and fee_schedule_match.get('feeSchedNum'):
                fee_sched_num = int(fee_schedule_match.get('feeSchedNum', 0))
                log(f"Fee schedule found - feeSchedNum: {fee_sched_num}")
                if fee_sched_num > 0:
                    plan_updates['FeeSched'] = fee_sched_num
                    log(f"Adding fee schedule to plan update: FeeSchedNum={fee_sched_num}")
                else:
                    log(f"Fee schedule num is 0 or invalid, not adding to plan updates")
            else:
                log(f"No fee schedule match found or missing data - found_fee_schedule: {fee_schedule_match.get('found_fee_schedule')}, feeSchedNum: {fee_schedule_match.get('feeSchedNum')}")
            
            if plan_updates:
                log(f"Updating existing plan {plan_num} with {len(plan_updates)} fields: {list(plan_updates.keys())}")
                log(f"Full plan_updates payload: {plan_updates}")
                update_result = self.update_insurance_plan(plan_num, plan_updates)
                log(f"Plan update result: {update_result}")
            else:
                log(f"No plan updates to apply for plan {plan_num}")
        
        # ---- PROCESS SUBSCRIBER ----
        log("Processing subscriber")
        
        if use_existing_subscriber:
            # User explicitly provided a subscriber
            ins_sub_num = existing_ins_sub_num
            log(f"Using user-provided subscriber: InsSubNum={ins_sub_num}")
            
            # Get the subscriber's patient record for family/guarantor relationships
            try:
                subscriber_details = self.make_request(f'/inssubs/{ins_sub_num}')
                if subscriber_details and 'Subscriber' in subscriber_details:
                    subscriber_pat_num = subscriber_details['Subscriber']
                    log(f"Retrieved subscriber patient: PatNum={subscriber_pat_num}")
            except Exception as e:
                log(f"Error retrieving subscriber patient details: {e}")
        elif plan_num:
            # Try to find matching subscriber for the existing plan
            matching_subscriber = self.find_matching_subscriber(plan_num, subscriber_id)
            
            if matching_subscriber:
                ins_sub_num = matching_subscriber['InsSubNum']
                log(f"Found matching subscriber: InsSubNum={ins_sub_num}")
                
                # Get subscriber patient details if this is a dependent relationship
                if not is_self_relationship:
                    subscriber_patient = self.find_subscriber_patient(form, subscriber_id)
                    if subscriber_patient and 'PatNum' in subscriber_patient:
                        subscriber_pat_num = subscriber_patient['PatNum']
                        log(f"Found subscriber patient: PatNum={subscriber_pat_num}")
        
        # For dependent relationships with no subscriber yet, find or create the subscriber patient
        if not is_self_relationship and not subscriber_pat_num:
            subscriber_fname = self.get_form_value(form, 'subscriber', 'subscriberFirstName', default='')
            subscriber_lname = self.get_form_value(form, 'subscriber', 'subscriberLastName', default='')
            subscriber_dob = self.get_form_value(form, 'subscriber', 'dateofBirth', default='')
            subscriber_dob_formatted = self.format_date(subscriber_dob)
            
            log(f"Looking for existing subscriber: {subscriber_fname} {subscriber_lname}, DOB={subscriber_dob_formatted}")
            
            existing_subscriber = self.find_existing_patient(subscriber_fname, subscriber_lname, subscriber_dob_formatted)
            if existing_subscriber and existing_subscriber.get('PatNum'):
                subscriber_pat_num = existing_subscriber['PatNum']
                log(f"Found existing subscriber patient: PatNum={subscriber_pat_num}")
            else:
                # Create new subscriber patient
                log(f"Creating new subscriber patient: {subscriber_fname} {subscriber_lname}")
                subscriber_data = {
                    'firstName': subscriber_fname,
                    'lastName': subscriber_lname,
                    'birthdate': subscriber_dob_formatted,
                    'carrierNum': carrier_num
                }
                subscriber_pat_num = self.create_patient(subscriber_data, address_fields)
                log(f"Created new subscriber patient: PatNum={subscriber_pat_num}")
        
        # ---- PROCESS PATIENT ----
        log("Processing patient")
        
        if use_existing_patient:
            # User explicitly provided a patient
            pat_num = existing_pat_num
            log(f"Using user-provided patient: PatNum={pat_num}")
        else:
            # Create new patient, with guarantor if dependent
            guarantor_for_dependent = None
            if not is_self_relationship and subscriber_pat_num:
                guarantor_for_dependent = subscriber_pat_num
                log(f"Setting guarantor for dependent: PatNum={guarantor_for_dependent}")
            
            pat_num = self.create_patient(patient_data, address_fields, guarantor_pat_num=guarantor_for_dependent)
            log(f"Created patient: PatNum={pat_num}")
        
        # ---- CREATE PLAN IF NEEDED ----
        if not plan_num:
            log("Creating new insurance plan")
            plan_type = self.get_form_value(form, 'planDetails', 'planType', default='')
            plan_type_value = self.PLAN_TYPES.get(plan_type.split(',')[0] if ',' in plan_type else plan_type, '')
            
            # Get fee schedule from form if provided
            fee_sched_name = self.get_form_value(form, 'planDetails', 'feeSchedule', default='')
            fee_sched_num = 0
            
            # Check if fee schedule was selected from pms_matches
            fee_schedule_match = patient_data.get('pms_matches', {}).get('fee_schedule_match', {})
            log(f"Checking fee schedule for new plan creation - fee_schedule_match: {fee_schedule_match}")
            if fee_schedule_match.get('found_fee_schedule') and fee_schedule_match.get('feeSchedNum'):
                fee_sched_num = int(fee_schedule_match.get('feeSchedNum', 0))
                log(f"Using fee schedule from pms_matches: FeeSchedNum={fee_sched_num}")
            else:
                log(f"No fee schedule match for new plan - found_fee_schedule: {fee_schedule_match.get('found_fee_schedule')}, feeSchedNum: {fee_schedule_match.get('feeSchedNum')}")
            
            plan_payload = {
                'CarrierNum': carrier_num,
                'GroupName': group_name,
                'GroupNum': group_num,
                'PlanNote': plan_note,
                'AssignBen': True,
                'ReleaseInfo': True,
                'PlanType': plan_type_value,
                'FeeSched': fee_sched_num  # Add fee schedule to plan creation
            }
            log(f"Creating new plan with payload: {plan_payload}")
            plan_response = self.make_request('/insplans', 'POST', plan_payload)
            plan_num = plan_response['PlanNum']
            log(f"Created new insurance plan: PlanNum={plan_num}, Response: {plan_response}")
            
            # Update pmsData with the new plan
            self.update_pms_data_with_plan(plan_num, group_name, group_num)
            log("Updated PMS data with new plan")
        
        # ---- CREATE INSURANCE SUBSCRIBER IF NEEDED ----
        if not ins_sub_num:
            log("Creating insurance subscriber record")
            
            # Determine subscriber for plan - for self, patient is subscriber
            # For dependent, use the subscriber patient we found/created
            subscriber_for_plan = subscriber_pat_num if not is_self_relationship and subscriber_pat_num else pat_num
            log(f"Determined subscriber for plan: PatNum={subscriber_for_plan}")
            
            # Build the request payload
            ins_sub_payload = {
                'PlanNum': plan_num,
                'Subscriber': subscriber_for_plan,
                'SubscriberID': self.get_form_value(form, 'subscriber', 'subscriberID', default=''),
                'ReleaseInfo': True,
                'AssignBen': True,
                'CarrierNum': carrier_num
            }
            
            # Only add DateEffective if it has a value
            if effective_date:
                ins_sub_payload['DateEffective'] = effective_date
                log(f"Including DateEffective: {effective_date}")
            else:
                log("DateEffective is empty, omitting from request")
                
            # Only add DateTerm if it has a value
            if termination_date:
                ins_sub_payload['DateTerm'] = termination_date
                log(f"Including DateTerm: {termination_date}")
            else:
                log("DateTerm is empty, omitting from request")
            
            ins_sub_response = self.make_request('/inssubs', 'POST', ins_sub_payload)
            ins_sub_num = ins_sub_response['InsSubNum']
            log(f"Created insurance subscriber: InsSubNum={ins_sub_num}")
        
        # ---- CREATE PATPLAN LINK IF NEEDED ----
        if not self.has_existing_patplan(pat_num, ins_sub_num):
            log(f"Creating PatPlan for patient {pat_num} with InsSubNum {ins_sub_num}")
            self.make_request('patplans', 'POST', {
                'PatNum': pat_num,
                'InsSubNum': ins_sub_num,
                'Ordinal': 1,
                'Relationship': self.normalize_relationship(relationship)
            })
            log("Created PatPlan linking patient to insurance")
        else:
            log(f"PatPlan already exists for patient {pat_num} with InsSubNum {ins_sub_num}")
        
        # ---- RETURN RESULT ----
        log("Basic patient setup completed successfully")
        
        return Ok({
            "message": "Basic patient setup completed",
            "data": {
                "patNum": pat_num,
                "planNum": plan_num,
                "carrierNum": carrier_num,
                "InsSubNum": ins_sub_num,
                "using_existing_plan": use_existing_plan,
                "using_existing_subscriber": use_existing_subscriber,
                "using_existing_patient": use_existing_patient
            }
        })

    def find_existing_patient(self, first_name: str, last_name: str, dob: str) -> dict:
        """Searches for an existing patient by name and DOB"""
        try:
            log(f"Searching for existing patient: {first_name} {last_name}, DOB: {dob}")
            
            # Search for patient with matching name
            patient_response = self.make_request(
                f'/patients/Simple?LName={last_name}&FName={first_name}&PatStatus=Patient'
            )
            
            if patient_response and len(patient_response) > 0:
                patient = patient_response[0]
                log(f"Found existing patient: {patient['FName']} {patient['LName']} {patient['PatNum']}")
                return patient
            
            log("No existing patient found")
            return {}
            
        except Exception as error:
            log(f"Error finding existing patient: {error}")
            return {}

    def find_matching_plan(self, group_name: str, group_num: str) -> dict:
        """
        Finds matching insurance plan in PMS data based solely on group number.
        Returns plan info if found, empty dict if not found.
        """
        try:
            if not group_num:
                log("No group number provided, cannot match plan")
                return {}
                
            log(f"Searching for matching plan with group number: {group_num}")
            
            insurance_plans = self.pms_data.get('insurancePlans', {})
            normalized_search_num = group_num.strip().upper()

            for stored_group_name, plan_data in insurance_plans.items():
                normalized_stored_num = plan_data.get('groupNum', '').strip().upper()
                
                if normalized_search_num == normalized_stored_num:
                    log(f"Found matching plan: {stored_group_name} with planNum: {plan_data['planNum']}")
                    return {
                        'planNum': plan_data['planNum'],
                        'groupName': stored_group_name,
                        'groupNum': plan_data['groupNum']
                    }
            
            log(f"No matching plan found for group number: {group_num}")
            return {}
        except Exception as e:
            log(f"Error finding matching plan: {e}")
            return {}

    def find_matching_subscriber(self, plan_num: int, subscriber_id: str) -> dict:
        """
        Searches for a matching subscriber by plan number and subscriber ID.
        Returns subscriber info if found, empty dict if not found.
        """
        try:
            log(f"Searching for subscriber with ID: {subscriber_id} in plan: {plan_num}")
            
            # Get all subscribers for this plan
            inssubs_response = self.make_request(f'/inssubs?PlanNum={plan_num}')
            
            if not inssubs_response:
                log("No subscribers found for this plan")
                return {}
            
            log(f"Found {len(inssubs_response)} subscribers in plan")
            
            # Look for matching subscriber ID
            for subscriber in inssubs_response:
                stored_id = subscriber.get('SubscriberID', '').strip()
                log(f"Checking subscriber: {stored_id}")
                
                if stored_id == subscriber_id.strip():
                    log(f"Match found! InsSubNum: {subscriber['InsSubNum']}")
                    return subscriber
                    
            log(f"No matching subscriber found in plan")
            return {}
            
        except Exception as error:
            log(f"Error in find_matching_subscriber: {error}")
            return {}
        
    def find_subscriber_patient(self, form: dict, subscriber_id: str) -> dict:
        """
        Finds the subscriber's patient record using name and birthdate.
        Returns patient info if found, empty dict if not found.
        """
        try:
            log(f"Looking up subscriber with ID: {subscriber_id}")
            
            # Get subscriber details from form
            subscriber_fname = self.get_form_value(form, 'subscriber', 'subscriberFirstName', default='')
            subscriber_lname = self.get_form_value(form, 'subscriber', 'subscriberLastName', default='')
            subscriber_dob_raw = self.get_form_value(form, 'subscriber', 'dateofBirth', default='')
            #format subscriber dob to YYYY-MM-DD
            subscriber_dob = self.format_date(subscriber_dob_raw)

            if not all([subscriber_fname, subscriber_lname, subscriber_dob]):
                log("Missing required subscriber information (name or formatted DOB)")
                return {}
                
            log(f"Searching for subscriber: {subscriber_fname} {subscriber_lname}, DOB: {subscriber_dob}")
            
            # Get patient details using Simple search
            patient_response = self.make_request(
                f'/patients/Simple?LName={subscriber_lname}&FName={subscriber_fname}&PatStatus=Patient'
            )
            
            if patient_response and len(patient_response) > 0:
                subscriber = patient_response[0]
                log(f"Found subscriber patient record: {subscriber['FName']} {subscriber['LName']} {subscriber['PatNum']}")
                return subscriber
            
            log("Subscriber patient record not found")
            return {}
            
        except Exception as error:
            log(f"Error finding subscriber patient: {error}")
            return {}

    def _benefits_are_different(self, new_benefit: dict, existing_benefit: dict,
                                value_fields_map: Dict[str, str], # e.g. {"Percent": "int", "MonetaryAmt": "float"}
                                epsilon: float = 0.001) -> Tuple[bool, List[str]]:
        """
        Compares specified fields between two benefits.
        Returns True if any field is different, along with a list of changed fields.
        """
        changed_fields_descriptions = []
        are_different = False

        for field_name, field_type in value_fields_map.items():
            new_val = new_benefit.get(field_name)
            existing_val = existing_benefit.get(field_name)

            # Consider default/unset values. OpenDental often uses -1 for unset int (Percent)
            # and -1.0 for unset float (MonetaryAmt), 0 for Quantity if not applicable.
            # A direct comparison should generally work.
            # If new_val is None and existing_val is a default like -1, they are different if we strictly compare.
            # However, if new_benefit provides a specific value (e.g. Percent=50)
            # and existing is default (Percent=-1), it's a clear change.

            field_has_changed = False
            if field_type == "float":
                # Attempt to convert to float for comparison, handle None or non-numeric gracefully
                try:
                    n_val = float(new_val) if new_val is not None else None
                    e_val = float(existing_val) if existing_val is not None else None
                    if n_val is not None and e_val is not None:
                        if abs(n_val - e_val) > epsilon:
                            field_has_changed = True
                    elif n_val != e_val: # One is None or they are otherwise different
                        field_has_changed = True
                except (ValueError, TypeError): # If conversion fails, compare as raw
                    if new_val != existing_val:
                        field_has_changed = True
            elif field_type == "int":
                try:
                    n_val = int(new_val) if new_val is not None else None
                    e_val = int(existing_val) if existing_val is not None else None
                    if n_val != e_val:
                        field_has_changed = True
                except (ValueError, TypeError):
                    if new_val != existing_val:
                         field_has_changed = True
            else:  # string or other
                if new_val != existing_val:
                    field_has_changed = True
            
            if field_has_changed:
                are_different = True
                changed_fields_descriptions.append(f"{field_name}: Old='{existing_val}', New='{new_val}'")
                
        return are_different, changed_fields_descriptions

    def _find_matching_coinsurance(self, new_benefit: dict, existing_typed_benefits: list) -> Tuple[Optional[dict], bool]:
        """Matches CoInsurance benefits. Keys: CovCatNum. Values: Percent."""
        new_cov_cat_num = new_benefit.get('CovCatNum', 0)
        value_fields = {"Percent": "int"}

        for eb in existing_typed_benefits:
            if eb.get('CovCatNum') == new_cov_cat_num:
                # Structural match found
                different, changes = self._benefits_are_different(new_benefit, eb, value_fields)
                if different:
                    log(f"CoInsurance match for CovCatNum {new_cov_cat_num} (BenefitNum {eb['BenefitNum']}): Values differ. Changes: {'; '.join(changes)}. Update needed.")
                else:
                    log(f"CoInsurance match for CovCatNum {new_cov_cat_num} (BenefitNum {eb['BenefitNum']}): Values identical. No update needed.")
                return eb, different
        return None, False

    def _find_matching_deductible(self, new_benefit: dict, existing_typed_benefits: list) -> Tuple[Optional[dict], bool]:
        """Matches Deductible benefits. Keys: CovCatNum, CoverageLevel, TimePeriod. Values: MonetaryAmt."""
        new_cov_cat_num = new_benefit.get('CovCatNum', 0) # 0 means general deductible
        new_coverage_level = new_benefit.get('CoverageLevel', 'None')
        new_time_period = new_benefit.get('TimePeriod', 'None')
        value_fields = {"MonetaryAmt": "float"}

        for eb in existing_typed_benefits:
            if (eb.get('CovCatNum', 0) == new_cov_cat_num and
                eb.get('CoverageLevel', 'None') == new_coverage_level and
                eb.get('TimePeriod', 'None') == new_time_period):
                # Structural match
                different, changes = self._benefits_are_different(new_benefit, eb, value_fields)
                log_msg_prefix = f"Deductible match (BenefitNum {eb['BenefitNum']}) for CovCatNum {new_cov_cat_num}, Level {new_coverage_level}, Period {new_time_period}:"
                if different:
                    log(f"{log_msg_prefix} Values differ. Changes: {'; '.join(changes)}. Update needed.")
                else:
                    log(f"{log_msg_prefix} Values identical. No update needed.")
                return eb, different
        return None, False

    def _find_matching_annual_max(self, new_benefit: dict, existing_typed_benefits: list) -> Tuple[Optional[dict], bool]:
        """Matches Annual Maximum (BenefitType='Limitations'). Keys: CoverageLevel, TimePeriod. Values: MonetaryAmt."""
        # Usually CodeGroupNum is 0 or not present for annual max
        new_coverage_level = new_benefit.get('CoverageLevel', 'None')
        new_time_period = new_benefit.get('TimePeriod', 'None')
        value_fields = {"MonetaryAmt": "float"}

        for eb in existing_typed_benefits:
            if (eb.get('CoverageLevel', 'None') == new_coverage_level and
                eb.get('TimePeriod', 'None') == new_time_period and
                eb.get('CodeGroupNum', 0) == 0 and # Ensure it's not a code-specific limitation
                eb.get('QuantityQualifier', 'None') not in ['AgeLimit', 'Months', 'Years', 'NumberOfServices']): # Ensure not frequency/age
                # Structural match
                different, changes = self._benefits_are_different(new_benefit, eb, value_fields)
                log_msg_prefix = f"Annual Max (Limitations BenefitNum {eb['BenefitNum']}) for Level {new_coverage_level}, Period {new_time_period}:"
                if different:
                    log(f"{log_msg_prefix} Values differ. Changes: {'; '.join(changes)}. Update needed.")
                else:
                    log(f"{log_msg_prefix} Values identical. No update needed.")
                return eb, different
        return None, False

    def _find_matching_frequency(self, new_benefit: dict, existing_typed_benefits: list) -> Tuple[Optional[dict], bool]:
        """Matches Frequency (BenefitType='Limitations'). Keys: CodeGroupNum. Values: Quantity, QuantityQualifier, TimePeriod."""
        new_code_group_num = new_benefit.get('CodeGroupNum', 0)
        # QuantityQualifier is key for type, TimePeriod for "per year"
        value_fields = {"Quantity": "int", "QuantityQualifier": "str", "TimePeriod": "str"}

        for eb in existing_typed_benefits:
            if (eb.get('CodeGroupNum', 0) == new_code_group_num and
                eb.get('QuantityQualifier') in ['Months', 'Years', 'NumberOfServices']): # Structural check for frequency
                # Structural match
                different, changes = self._benefits_are_different(new_benefit, eb, value_fields)
                log_msg_prefix = f"Frequency Limitation (BenefitNum {eb['BenefitNum']}) for CodeGroupNum {new_code_group_num}:"
                if different:
                    log(f"{log_msg_prefix} Values differ. Changes: {'; '.join(changes)}. Update needed.")
                else:
                    log(f"{log_msg_prefix} Values identical. No update needed.")
                return eb, different
        return None, False

    def _find_matching_age_limit(self, new_benefit: dict, existing_typed_benefits: list) -> Tuple[Optional[dict], bool]:
        """Matches Age Limit (BenefitType='Limitations', QtyQualifier='AgeLimit'). Keys: CodeGroupNum. Values: Quantity."""
        new_code_group_num = new_benefit.get('CodeGroupNum', 0)
        value_fields = {"Quantity": "int"} # QuantityQualifier is 'AgeLimit' by definition here

        for eb in existing_typed_benefits:
            if (eb.get('CodeGroupNum', 0) == new_code_group_num and
                eb.get('QuantityQualifier') == 'AgeLimit'): # Structural check
                # Structural match
                different, changes = self._benefits_are_different(new_benefit, eb, value_fields)
                log_msg_prefix = f"Age Limitation (BenefitNum {eb['BenefitNum']}) for CodeGroupNum {new_code_group_num}:"
                if different:
                    log(f"{log_msg_prefix} Values differ. Changes: {'; '.join(changes)}. Update needed.")
                else:
                    log(f"{log_msg_prefix} Values identical. No update needed.")
                return eb, different
        return None, False

    def _find_matching_waiting_period(self, new_benefit: dict, existing_typed_benefits: list) -> Tuple[Optional[dict], bool]:
        """Matches WaitingPeriod benefits. Keys: CovCatNum. Values: Quantity, QuantityQualifier."""
        new_cov_cat_num = new_benefit.get('CovCatNum', 0)
        value_fields = {"Quantity": "int", "QuantityQualifier": "str"}

        for eb in existing_typed_benefits:
            if eb.get('CovCatNum', 0) == new_cov_cat_num:
                # Structural match
                different, changes = self._benefits_are_different(new_benefit, eb, value_fields)
                log_msg_prefix = f"Waiting Period (BenefitNum {eb['BenefitNum']}) for CovCatNum {new_cov_cat_num}:"
                if different:
                    log(f"{log_msg_prefix} Values differ. Changes: {'; '.join(changes)}. Update needed.")
                else:
                    log(f"{log_msg_prefix} Values identical. No update needed.")
                return eb, different
        return None, False

    def _find_matching_generic(self, new_benefit: dict, existing_typed_benefits: list) -> Tuple[Optional[dict], bool]:
        """
        Fallback matcher for generic benefits.
        Finds the first structurally similar benefit and assumes update is needed
        as specific value comparison rules are not defined.
        """
        # This is a simplified generic matcher. It looks for some common keys.
        # If a benefit shares a few identifying characteristics, we assume it's the one.
        # Since we don't have specific value comparison rules, we'll say it needs an update.
        new_cov_cat = new_benefit.get('CovCatNum')
        new_code_group = new_benefit.get('CodeGroupNum')
        new_code_num = new_benefit.get('CodeNum') # specific procedure code
        new_coverage_level = new_benefit.get('CoverageLevel')

        for eb in existing_typed_benefits:
            # Try to match based on a hierarchy of available keys in new_benefit
            match_score = 0
            potential_match = False

            if new_code_num and eb.get('CodeNum') == new_code_num: # Strongest individual match
                potential_match = True
            elif new_code_group and new_code_group > 0 and eb.get('CodeGroupNum') == new_code_group:
                # If CodeGroupNum matches, check CoverageLevel too if present
                if new_coverage_level and new_coverage_level != "None" and eb.get('CoverageLevel') == new_coverage_level:
                    potential_match = True
                elif not (new_coverage_level and new_coverage_level != "None"): # No specific coverage level
                    potential_match = True
            elif new_cov_cat and new_cov_cat > 0 and eb.get('CovCatNum') == new_cov_cat:
                 # If CovCatNum matches, check CoverageLevel too if present
                if new_coverage_level and new_coverage_level != "None" and eb.get('CoverageLevel') == new_coverage_level:
                    potential_match = True
                elif not (new_coverage_level and new_coverage_level != "None"):
                    potential_match = True
            
            # If it's a very generic new_benefit (no specific codes/cats)
            # just matching on CoverageLevel might be too broad.
            # This generic matcher might need more refinement based on observed generic benefit types.

            if potential_match:
                log(f"Generic benefit match found for new benefit (type {new_benefit.get('BenefitType')}) with existing BenefitNum {eb['BenefitNum']}. Assuming update needed due to generic nature.")
                return eb, True # Assume update needed for generic matches

        log(f"No generic structural match found for new benefit (type {new_benefit.get('BenefitType')}).")
        return None, False

    def find_matching_benefit(self, new_benefit: dict, existing_benefits: list) -> Tuple[Optional[dict], bool]:
        """
        Enhanced benefit matching that returns (matching_benefit, needs_update_bool).
        Dispatches to type-specific finders.
        """
        if not existing_benefits:
            return None, False

        benefit_type = new_benefit.get('BenefitType')
        log(f"Finding matching benefit for Type: {benefit_type}, New Benefit Keys: {list(new_benefit.keys())}")

        # Filter by benefit type first for efficiency
        type_matches = [b for b in existing_benefits if b.get('BenefitType') == benefit_type]
        if not type_matches:
            log(f"No existing benefits of type '{benefit_type}' found.")
            return None, False
        
        log(f"Found {len(type_matches)} existing benefits of type '{benefit_type}'.")

        if benefit_type == 'CoInsurance':
            return self._find_matching_coinsurance(new_benefit, type_matches)
        elif benefit_type == 'Deductible':
            return self._find_matching_deductible(new_benefit, type_matches)
        elif benefit_type == 'WaitingPeriod':
            return self._find_matching_waiting_period(new_benefit, type_matches)
        elif benefit_type == 'Limitations':
            # Limitations need further dispatch based on QuantityQualifier or other fields
            qty_qualifier = new_benefit.get('QuantityQualifier')
            code_group_num = new_benefit.get('CodeGroupNum', 0)
            monetary_amt = new_benefit.get('MonetaryAmt', -1.0)

            if qty_qualifier == 'AgeLimit' and code_group_num > 0:
                return self._find_matching_age_limit(new_benefit, type_matches)
            elif qty_qualifier in ['Months', 'Years', 'NumberOfServices'] and code_group_num > 0:
                return self._find_matching_frequency(new_benefit, type_matches)
            elif monetary_amt > -1.0 and code_group_num == 0 : # Likely an Annual Max
                 # Ensure it's not also an age/frequency by checking qty_qualifier
                if qty_qualifier not in ['AgeLimit', 'Months', 'Years', 'NumberOfServices']:
                    return self._find_matching_annual_max(new_benefit, type_matches)
                else: # It has monetary amount but also seems like a frequency/age limit based on QtyQualifier
                    log(f"Limitations benefit for CodeGroup {code_group_num} has MonetaryAmt AND QtyQualifier '{qty_qualifier}'. Falling to generic.")
                    return self._find_matching_generic(new_benefit, type_matches) # Fallback for ambiguous
            else: # Other 'Limitations' type
                log(f"Unhandled 'Limitations' subtype (QtyQual: {qty_qualifier}, CodeGroup: {code_group_num}, MonetaryAmt: {monetary_amt}). Falling to generic.")
                return self._find_matching_generic(new_benefit, type_matches)
        
        # Fall back to generic matching for other types
        log(f"Benefit type '{benefit_type}' not specifically handled, using generic matcher.")
        return self._find_matching_generic(new_benefit, type_matches)

    def clean_percentage(self, value: str) -> int:
        """Cleans percentage values by removing % and converting to int"""
        if not value:
            return 0
        try:
            # Remove % symbol and any whitespace, then convert to int
            cleaned = str(value).replace('%', '').strip()
            return int(cleaned)
        except (ValueError, TypeError) as e:
            log(f"Invalid percentage value '{value}': {e}")
            return 0

    def process_benefits_dynamically(self, form: dict, benefits_to_create: list) -> None:
        """Process all benefits dynamically based on the form data."""
        # Determine the single, authoritative TimePeriod for the plan
        plan_wide_time_period = ("CalendarYear" if 'calendar' in 
                               form.get('maximumsAndDeductibles', {}).get('benefitYear', {}).get('value', '').lower() 
                               else "ServiceYear")
        log(f"Plan-wide TimePeriod determined as: {plan_wide_time_period}")

        self._process_coverage_percentages(form, benefits_to_create)
        self._process_maximums_and_deductibles(form, benefits_to_create, plan_wide_time_period) # Pass it here
        self._process_waiting_periods(form, benefits_to_create)
        self._process_procedure_benefits(form, benefits_to_create, plan_wide_time_period) # Pass it here
        self._process_age_limits(form, benefits_to_create)

    def process_benefits_in_parallel(self, benefits_to_create: list, existing_benefits=None) -> dict:
        """
        Process multiple benefits in parallel using Celery tasks.
        
        Args:
            benefits_to_create: List of benefits to create/update
            existing_benefits: List of existing benefits to check against
            
        Returns:
            dict: Results including successful count, updated count, and failure count
        """
        from backend.services.task_hub.benefits_tasks.od_benefit_tasks import process_single_benefit
        
        log("Processing benefits in parallel using Celery tasks")
        
        # Queue up all the tasks
        tasks = []
        skipped_updates_count = 0 # Initialize skipped updates counter
        for benefit in benefits_to_create:
            # Find matching benefit if using existing plan
            matching_benefit = None
            needs_update = True # Default to True for create, or if match found and values differ
            
            if existing_benefits:
                matching_benefit, needs_update = self.find_matching_benefit(benefit, existing_benefits)
                if matching_benefit:
                    if needs_update:
                        log(f"Found matching benefit {matching_benefit.get('BenefitNum')} for {benefit.get('BenefitType')} (CovCat: {benefit.get('CovCatNum', 'N/A')}, CodeGroup: {benefit.get('CodeGroupNum', 'N/A')}) and values differ. Will update.")
                    else:
                        log(f"Found matching benefit {matching_benefit.get('BenefitNum')} for {benefit.get('BenefitType')} (CovCat: {benefit.get('CovCatNum', 'N/A')}, CodeGroup: {benefit.get('CodeGroupNum', 'N/A')}) but values are identical. Skipping update.")
                else: # No structural match found
                    log(f"No matching benefit found for {benefit.get('BenefitType')} (CovCat: {benefit.get('CovCatNum', 'N/A')}, CodeGroup: {benefit.get('CodeGroupNum', 'N/A')}). Will create.")
                    needs_update = True # Ensure creation happens
            else: # No existing benefits, so definitely a create
                log(f"No existing benefits for plan, will create new {benefit.get('BenefitType')} (CovCat: {benefit.get('CovCatNum', 'N/A')}, CodeGroup: {benefit.get('CodeGroupNum', 'N/A')}).")
                needs_update = True # Ensure creation happens

            if not matching_benefit or needs_update: # Create if no match, or if match found and needs update
                # If matching_benefit exists but needs_update is True, it's an update.
                # If matching_benefit is None, it's a create (needs_update will also be True).
                task = process_single_benefit.delay(
                    benefit_data=benefit,
                    matching_benefit_data=matching_benefit if needs_update and matching_benefit else None, # Pass match only if updating
                    base_url=self.base_url,
                    auth_token=self.auth_token
                )
                # Second element indicates if it's an update task (True) or create task (False)
                tasks.append((task, matching_benefit is not None and needs_update))
            else:
                # This is where we count skipped updates because a match was found AND values were identical
                skipped_updates_count += 1
        
        log(f"Queued {len(tasks)} benefit processing tasks in parallel. Skipped {skipped_updates_count} updates due to identical values.")
        
        # Wait for all tasks to complete and collect results
        successful_benefits = 0
        updated_benefits = 0
        failed_benefits = 0
        # skipped_updates_count is already tallied above
        
        for task, is_update_task in tasks:
            try:
                # Wait for each task with a reasonable timeout
                result = task.get(timeout=60)
                
                # Collect API call details from task result and add to self.api_responses
                if result and isinstance(result.get('api_call_details'), list):
                    for call_detail in result['api_call_details']:
                        # Ensure the structure matches what make_request logs, if necessary
                        # Current structure from od_benefit_tasks.py:
                        # {'timestamp', 'method', 'url', 'request_payload', 'status_code', 'response_body'}
                        # Current structure from make_request:
                        # {'timestamp', 'method', 'endpoint', 'request_data', 'status_code', 'response_json'}
                        # We can adapt here or ensure od_benefit_tasks.py uses 'endpoint' and 'request_data' keys.
                        # For now, let's append as is, and note the potential key differences.
                        adapted_call_detail = {
                            'timestamp': call_detail.get('timestamp'),
                            'method': call_detail.get('method'),
                            'endpoint': call_detail.get('url'), # Assuming URL can be treated as endpoint
                            'request_data': call_detail.get('request_payload'),
                            'status_code': call_detail.get('status_code'),
                            'response_json': call_detail.get('response_body'), # Assuming body is JSON or compatible
                            'source_task': 'process_single_benefit' # Add source for clarity
                        }
                        self.api_responses.append(adapted_call_detail)
                
                if result.get('success', False):
                    successful_benefits += 1
                    benefit_desc_from_task = result.get('benefit_details_desc', 'Details N/A') # Get detailed description
                    if result.get('is_update', False):
                        updated_benefits += 1
                        log(f"Celery task: Successfully UPDATED benefit. Details: {benefit_desc_from_task}")
                    else:
                        log(f"Celery task: Successfully CREATED benefit. Details: {benefit_desc_from_task}")
                else:
                    failed_benefits += 1
                    benefit_desc_from_task = result.get('benefit_details_desc', 'Details N/A') # Get detailed description
                    log(f"Celery task: FAILED to process benefit. Details: {benefit_desc_from_task}. Error: {result.get('error', 'Unknown error')}")
            except Exception as e:
                failed_benefits += 1
                # Construct a description for the benefit that caused the task retrieval error
                benefit_type_for_error = benefit.get('BenefitType', 'Unknown') # Assuming 'benefit' is accessible here from the loop
                benefit_plan_num_for_error = benefit.get('PlanNum', 'N/A')
                error_benefit_desc = f"Type: {benefit_type_for_error}, PlanNum: {benefit_plan_num_for_error}"
                if benefit.get('CovCatNum'): error_benefit_desc += f", CovCatNum: {benefit.get('CovCatNum')}"
                if benefit.get('CodeGroupNum'): error_benefit_desc += f", CodeGroupNum: {benefit.get('CodeGroupNum')}"
                if matching_benefit and matching_benefit.get('BenefitNum'): error_benefit_desc += f", BenefitNum: {matching_benefit.get('BenefitNum')}"
                log(f"Error retrieving task result for benefit processing. Benefit Details: {error_benefit_desc}. Error: {e}")
        
        log(f"Parallel benefits processing complete - Created: {successful_benefits - updated_benefits}, "
            f"Updated: {updated_benefits}, Failed: {failed_benefits}, Skipped: {skipped_updates_count}")
        
        return {
            "successful": successful_benefits,
            "updated": updated_benefits,
            "failed": failed_benefits,
            "skipped": skipped_updates_count,
            "total_processed_via_api": len(tasks),
            "total_considered": len(benefits_to_create) # Total initially considered
        }

    def _create_benefit(self, benefit_type: str, **kwargs) -> dict:
        """Creates a benefit with the given type and additional fields"""
        benefit = {
            "PlanNum": self.plan_num,
            "BenefitType": benefit_type,
            "CoverageLevel": kwargs.get("CoverageLevel", "None"),
            "Percent": kwargs.get("Percent", -1),
            "MonetaryAmt": kwargs.get("MonetaryAmt", -1.0),
            "TimePeriod": kwargs.get("TimePeriod", "None"),
            "QuantityQualifier": kwargs.get("QuantityQualifier", "None"),
            "Quantity": kwargs.get("Quantity", 0)
        }
        benefit.update({k: v for k, v in kwargs.items() if k not in benefit})
        return benefit

    def _process_coverage_percentages(self, form: dict, benefits: list) -> None:
        """Process coverage percentages dynamically"""
        coverage = form.get('coveragePercentages', {})
        for field_name, field_data in coverage.items():
            if not field_name.endswith('Percentage'): continue
            try:
                percentage = field_data.get('value', '')
                if not percentage: continue
                clean_percent = self.clean_percentage(percentage)
                if clean_percent <= 0: continue
                
                # Extract category name from field name
                # Example: "diagnosticPercentage" -> "diagnostic"
                category_key_from_field = field_name.replace('Percentage', '')
                
                # Find the matching CovCatNum. self.cov_cats uses original names from pmsData.
                # We need to find a key in self.cov_cats that, when normalized (like in router),
                # matches category_key_from_field.
                cov_cat_num = 0
                found_cat_name = None
                for pms_cat_name in self.cov_cats.keys():
                    normalized_pms_cat_name = pms_cat_name.lower().replace(' ', '').replace('-', '').replace('_', '')
                    if normalized_pms_cat_name == category_key_from_field:
                        cov_cat_num = self.cov_cats[pms_cat_name]
                        found_cat_name = pms_cat_name
                        break
                
                if cov_cat_num == 0:
                    log(f"Warning: Could not find CovCatNum for percentage field: {field_name} (derived key: {category_key_from_field})")
                    continue
                    
                log(f"Processing coverage for category: {found_cat_name} ({cov_cat_num}) with {clean_percent}%")
                benefits.append(self._create_benefit(
                    "CoInsurance",
                    Percent=clean_percent,
                    CovCatNum=cov_cat_num
                ))
            except Exception as e:
                log(f"Error processing coverage percentage for {field_name}: {e}")
    
    def _process_maximums_and_deductibles(self, form: dict, benefits: list, plan_wide_time_period: str) -> None:
        """Process maximums and deductibles dynamically, using the provided plan_wide_time_period."""
        max_deduct = form.get('maximumsAndDeductibles', {})
        
        def clean_amount(amount: Any) -> float:
            if not amount or not isinstance(amount, (str, int, float)): return 0.0
            try:
                cleaned = str(amount).upper().strip()
                if cleaned in ['NO', 'N/A', 'NONE', 'N', '']: return 0.0
                if cleaned in ['YES', 'Y']: return 0.0 # Changed from 1.0 to 0.0
                return float(str(amount).replace(',', '').replace('$', ''))
            except (ValueError, TypeError) as e:
                log(f"Error cleaning amount '{amount}': {e}")
                return 0.0
        
        # Process annual maximum
        try:
            annual_max = clean_amount(max_deduct.get('AnnualMax', {}).get('value'))
            if annual_max > 0:
                benefits.append(self._create_benefit(
                    "Limitations",
                    CoverageLevel="Individual", # Or Family if there's a separate family max field
                    MonetaryAmt=annual_max,
                    TimePeriod=plan_wide_time_period # Use passed-in value
                ))
        except Exception as e:
            log(f"Error processing annual maximum: {e}")
        
        # Process standard deductibles (individual/family for overall plan)
        for field_name in ['individualDeductible', 'familyDeductible']:
            try:
                deduct_amount = clean_amount(max_deduct.get(field_name, {}).get('value'))
                if deduct_amount > 0:
                    coverage_level = 'Individual' if field_name == 'individualDeductible' else 'Family'
                    benefits.append(self._create_benefit(
                        "Deductible",
                        CoverageLevel=coverage_level,
                        MonetaryAmt=deduct_amount,
                        TimePeriod=plan_wide_time_period # Use passed-in value
                    ))
            except Exception as e:
                log(f"Error processing {field_name}: {e}")
        
        # Process category-specific deductibles from the coveragePercentages section
        coverage_data = form.get('coveragePercentages', {})
        for field_name, field_data in coverage_data.items():
            if not field_name.endswith('Deductible'): continue
            try:
                deduct_amount = clean_amount(field_data.get('value'))
                if deduct_amount <= 0: continue
                
                category_key_from_field = field_name.replace('Deductible', '')
                cov_cat_num = 0
                found_cat_name = None
                for pms_cat_name in self.cov_cats.keys():
                    normalized_pms_cat_name = pms_cat_name.lower().replace(' ', '').replace('-', '').replace('_', '')
                    if normalized_pms_cat_name == category_key_from_field:
                        cov_cat_num = self.cov_cats[pms_cat_name]
                        found_cat_name = pms_cat_name
                        break

                if cov_cat_num > 0:
                    log(f"Processing deductible for category: {found_cat_name} ({cov_cat_num}) with amount {deduct_amount}")
                    benefits.append(self._create_benefit(
                        "Deductible",
                        CoverageLevel="Individual", # Category deductibles usually individual, unless specified
                        MonetaryAmt=deduct_amount,
                        TimePeriod=plan_wide_time_period, # Use passed-in value
                        CovCatNum=cov_cat_num
                    ))
                else:
                    log(f"Warning: Could not find CovCatNum for deductible field: {field_name} (derived key: {category_key_from_field})")
            except Exception as e:
                log(f"Error processing category deductible for {field_name}: {e}")
    
    def _process_waiting_periods(self, form: dict, benefits: list) -> None:
        """Process waiting periods dynamically from the coveragePercentages section"""
        coverage_data = form.get('coveragePercentages', {})
        
        for field_name, field_data in coverage_data.items():
            if not field_name.endswith('WaitingPeriod'): continue
            period_value_str = field_data.get('value', '')
            if not period_value_str or period_value_str.lower().strip() in ['none', 'n/a', 'no', '0']:
                continue
            
            try:
                # Parse waiting period with proper month/year handling
                months = self._parse_waiting_period_to_months(period_value_str)
                if months <= 0: continue
                
                category_key_from_field = field_name.replace('WaitingPeriod', '')
                cov_cat_num = 0
                found_cat_name = None
                for pms_cat_name in self.cov_cats.keys():
                    normalized_pms_cat_name = pms_cat_name.lower().replace(' ', '').replace('-', '').replace('_', '')
                    if normalized_pms_cat_name == category_key_from_field:
                        cov_cat_num = self.cov_cats[pms_cat_name]
                        found_cat_name = pms_cat_name
                        break
                
                if cov_cat_num == 0:
                    log(f"Warning: Could not find CovCatNum for waiting period field: {field_name} (derived key: {category_key_from_field})")
                    continue
                
                log(f"Processing waiting period for category: {found_cat_name} ({cov_cat_num}) of {months} months (from '{period_value_str}')")
                benefits.append(self._create_benefit(
                    "WaitingPeriod",
                    CovCatNum=cov_cat_num,
                    QuantityQualifier="Months",
                    Quantity=months
                ))
            except (ValueError, TypeError) as e: 
                log(f"Error processing waiting period for {field_name} (value: {period_value_str}): {e}")
                continue

    def _parse_waiting_period_to_months(self, period_value_str: str) -> int:
        """
        Parse waiting period string to months, handling various formats.
        
        Examples:
        - "6 months" -> 6
        - "1 year" -> 12  
        - "2 years" -> 24
        - "12" -> 12 (assumes months if no unit)
        - "18 month" -> 18
        - "1.5 years" -> 18
        
        Returns:
        - int: Number of months, or 0 if parsing fails
        """
        if not period_value_str:
            return 0
            
        # Normalize the string for parsing
        normalized = str(period_value_str).lower().strip()
        
        # Extract number (including decimals)
        number_match = re.search(r'(\d+(?:\.\d+)?)', normalized)
        if not number_match:
            log(f"Warning: No number found in waiting period '{period_value_str}'")
            return 0
            
        try:
            number = float(number_match.group(1))
        except (ValueError, TypeError):
            log(f"Warning: Could not parse number from waiting period '{period_value_str}'")
            return 0
            
        # Determine the unit
        if any(unit in normalized for unit in ['year', 'yr', 'annual']):
            # Convert years to months
            months = int(number * 12)
            log(f"Parsed '{period_value_str}' as {number} year(s) = {months} months")
        elif any(unit in normalized for unit in ['month', 'mo', 'mth']):
            # Already in months
            months = int(number)
            log(f"Parsed '{period_value_str}' as {months} months")
        else:
            # No unit specified, assume months
            months = int(number)
            log(f"Parsed '{period_value_str}' as {months} months (no unit specified, assumed months)")
            
        return max(0, months)  # Ensure non-negative

    def _process_procedure_benefits(self, form: dict, benefits: list, plan_wide_time_period: str) -> None:
        """Process procedure benefits dynamically from the 'procedures' section, using plan_wide_time_period."""
        procedures_data = form.get('procedures', {}) # Changed from hardcoded categories
        if not procedures_data:
            log("No 'procedures' section found in form_data or it is empty.")
            return

        for proc_code_from_form, proc_data_container in procedures_data.items():
            try:
                # proc_code_from_form is the key from the procedures section (e.g., "BW", "Exam")
                # This should ideally be the standard name as per pmsData.codeGroups
                if not isinstance(proc_data_container, dict) or 'value' not in proc_data_container:
                    log(f"Skipping procedure {proc_code_from_form}: 'value' key missing or invalid structure.")
                    continue
                proc_value_dict = proc_data_container['value']
                if not isinstance(proc_value_dict, dict):
                    log(f"Skipping procedure {proc_code_from_form}: value under 'value' key is not a dictionary.")
                    continue

                # Get frequency string and parse it
                frequency_str = str(proc_value_dict.get('frequency', '')).strip()
                
                # Backwards compatibility: check for old format fields if no frequency provided
                if not frequency_str:
                    per_year_str = str(proc_value_dict.get('perYear', '')).strip()
                    months_str = str(proc_value_dict.get('months', '')).strip()
                    years_str = str(proc_value_dict.get('years', '')).strip()
                    
                    # Convert old format to new frequency string
                    if per_year_str and per_year_str.isdigit() and int(per_year_str) > 0:
                        frequency_str = f"{per_year_str} per year"
                        log(f"Backwards compatibility: converted perYear='{per_year_str}' to frequency='{frequency_str}'")
                    elif months_str and months_str.isdigit() and int(months_str) > 0:
                        frequency_str = f"{months_str} months"
                        log(f"Backwards compatibility: converted months='{months_str}' to frequency='{frequency_str}'")
                    elif years_str and years_str.isdigit() and int(years_str) > 0:
                        frequency_str = f"{years_str} years"
                        log(f"Backwards compatibility: converted years='{years_str}' to frequency='{frequency_str}'")
                
                if not frequency_str:
                    # Skip if no frequency provided in either format
                    continue

                # Parse the frequency string using our new parser
                unit, freq_value = self._parse_frequency_string(frequency_str)
                
                if unit == 0 or freq_value <= 0:
                    log(f"No valid frequency found for procedure {proc_code_from_form} (input: '{frequency_str}'). Skipping frequency benefit.")
                    continue

                # Use proc_code_from_form directly as it's expected to be the standard group name
                # The get_code_group_num will use the (now dynamic) ProcedureNameMapper if needed,
                # but ideally proc_code_from_form is already the standard name.
                log(f"Creating frequency benefit for procedure: {proc_code_from_form} (Unit: {unit}, Freq: {freq_value}, Input: '{frequency_str}') using TimePeriod: {plan_wide_time_period} for 'per year' type")
                if benefit := self.create_procedure_benefit(proc_code_from_form, unit, freq_value, plan_wide_time_period):
                    benefits.append(benefit)
                else:
                    log(f"Failed to create procedure benefit for {proc_code_from_form}")

            except Exception as e:
                log(f"Error processing procedure benefit for {proc_code_from_form}: {e}")
    
    def _process_age_limits(self, form: dict, benefits: list) -> None:
        """Process age limits dynamically from the 'procedures' section"""
        procedures_data = form.get('procedures', {}) # Changed from hardcoded categories
        if not procedures_data:
            log("No 'procedures' section found in form_data for age limits or it is empty.")
            return

        for proc_code_from_form, proc_data_container in procedures_data.items():
            try:
                if not isinstance(proc_data_container, dict) or 'value' not in proc_data_container:
                    log(f"Skipping age limit for procedure {proc_code_from_form}: 'value' key missing or invalid structure.")
                    continue
                proc_value_dict = proc_data_container['value']
                if not isinstance(proc_value_dict, dict):
                    log(f"Skipping age limit for procedure {proc_code_from_form}: value under 'value' key is not a dictionary.")
                    continue

                age_limit_str = str(proc_value_dict.get('ageLimit', '')).strip()
                if not age_limit_str or not age_limit_str.isdigit():
                    # log(f"No valid age limit found for procedure {proc_code_from_form}. Skipping age limit benefit.")
                    continue
                
                age_limit = int(age_limit_str)
                if age_limit <= 0:
                    log(f"Age limit is zero or less for {proc_code_from_form}. Skipping age limit benefit.")
                    continue
                    
                # Use proc_code_from_form, expecting it to be a standard group name
                group_num = self.get_code_group_num(proc_code_from_form)
                if group_num > 0:
                    log(f"Creating age limit benefit for procedure: {proc_code_from_form} (Age: {age_limit}, GroupNum: {group_num})")
                    benefits.append({
                        "PlanNum": self.plan_num,
                        "BenefitType": "Limitations",
                        "CoverageLevel": "None", 
                        "TimePeriod": "None", 
                        "QuantityQualifier": "AgeLimit",
                        "Quantity": age_limit,
                        "CodeGroupNum": group_num,
                        "Percent": -1,    
                        "MonetaryAmt": -1,
                    })
                else:
                    log(f"Warning: Could not find CodeGroupNum for procedure {proc_code_from_form} when creating age limit benefit.")
            except (ValueError, TypeError) as e:
                log(f"Error processing age limit for {proc_code_from_form} (value: {age_limit_str}): {e}")
                continue       

    def create_procedure_benefit(self, group_name: str, unit: int, frequency: int, plan_wide_time_period: str) -> dict:
        """Creates procedure-specific benefit with frequency information.
        group_name is expected to be the standard procedure group name from pmsData.codeGroups.
        plan_wide_time_period is used for 'X per year' type limitations.
        """
        try:
            # group_name should be the standard name. get_code_group_num uses the mapper if needed.
            code_group_num = self.get_code_group_num(group_name) 
            if code_group_num == 0: 
                log(f"Warning: No code group found for procedure group name '{group_name}' when creating procedure benefit.")
                return None

            # Handle different time periods based on unit type
            if unit == 3:  # X per year
                return self._create_benefit(
                    "Limitations",
                    CodeGroupNum=code_group_num,
                    TimePeriod=plan_wide_time_period, # Use the plan-wide time period here
                    QuantityQualifier="NumberOfServices",
                    Quantity=frequency
                )
            elif unit == 2:  # Every X years
                return self._create_benefit(
                    "Limitations",
                    CodeGroupNum=code_group_num,
                    TimePeriod="None",
                    QuantityQualifier="Years",
                    Quantity=frequency
                )
            else:  # unit == 1: Every X months
                return self._create_benefit(
                    "Limitations",
                    CodeGroupNum=code_group_num,
                    TimePeriod="None",
                    QuantityQualifier="Months",
                    Quantity=frequency
                )
        except Exception as e:
            log(f"Error creating procedure benefit for {group_name}: {e}")
            return None

    def upload_document(self, pat_num: int, base64_image: str, docCategory: int, description: str = "Insurance Verification Form") -> dict:
        """Uploads a single document to OpenDental with PDF support"""
        log(f"Starting document upload for patient {pat_num}")
        
        try:
            if not base64_image:
                log("No document data provided")
                return Err("No document data provided.")

            try:
                log("Decoding base64 image data")
                file_bytes = base64.b64decode(base64_image)
                log("Base64 decode successful")
            except (TypeError, ValueError, base64.binascii.Error) as decode_error:
                log(f"Initial base64 decode failed: {decode_error}, attempting cleaning...")
                
                cleaned_base64 = ''.join(str(base64_image).split())
                
                if not cleaned_base64:
                     log("Base64 string is empty after cleaning")
                     return Err("Provided base64 string is invalid or empty after cleaning.")

                missing_padding = len(cleaned_base64) % 4
                if missing_padding:
                    cleaned_base64 += '=' * (4 - missing_padding)

                try:
                    file_bytes = base64.b64decode(cleaned_base64)
                    base64_image = cleaned_base64
                    log("Successfully decoded base64 string after cleaning")
                except Exception as inner_decode_error:
                     log(f"Error decoding cleaned base64 string: {inner_decode_error}")
                     return Err(f"Invalid base64 string provided even after cleaning: {inner_decode_error}")
            
            is_pdf = file_bytes[:5].startswith(b'%PDF')
            log(f"Detected document type: {'PDF' if is_pdf else 'Image'}")
            
            log(f"Preparing document upload request for {len(file_bytes)} bytes")
            doc_data = {
                "PatNum": pat_num,
                "rawBase64": base64_image,
                "Description": description,
                "DateCreated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "DocCategory": docCategory,
                "extension": ".pdf" if is_pdf else ".jpg",
                "ImgType": "Document" if is_pdf else "Photo"
            }
            
            log("Sending document upload request to OpenDental")
            response = self.make_request('documents/Upload', 'POST', doc_data)
            
            log("Document upload completed successfully")
            
            return Ok({
                "message": "Document uploaded successfully", 
                "data": response
            })
                
        except Exception as error:
            log(f"Error in upload_document: {error}")
            return Err(f"Failed to upload document: {str(error)}")

    def _parse_frequency_string(self, frequency_str: str) -> Tuple[int, int]:
        """
        Parse frequency string to extract unit and frequency value.
        
        This method handles natural language frequency inputs and converts them to OpenDental
        benefit structures. It supports various formats including:
        
        EXAMPLES:
        Input Format                 -> Output (unit, freq) -> OpenDental Benefit
        -------------------------------------------------------------------------
        "2 per year"                -> (3, 2)              -> 2 services per year
        "1 per 6 months"            -> (1, 6)              -> once every 6 months  
        "1 per 2 years"             -> (2, 2)              -> once every 2 years
        "6 months"                  -> (1, 6)              -> once every 6 months
        "2 years"                   -> (2, 2)              -> once every 2 years
        "2"                         -> (3, 2)              -> 2 per year (default)
        "every 6 months"            -> (1, 6)              -> once every 6 months
        "every 2 years"             -> (2, 2)              -> once every 2 years
        "twice per year"            -> (3, 2)              -> 2 services per year
        "once per year"             -> (3, 1)              -> 1 service per year
        "annually"                  -> (3, 1)              -> once per year
        "biannually"                -> (3, 2)              -> twice per year
        "monthly"                   -> (1, 1)              -> once per month
        "quarterly"                 -> (1, 3)              -> once every 3 months
        
        FORM DATA STRUCTURE:
        The normalized form data would look like:
        {
            "procedures": {
                "BW": {
                    "value": {
                        "frequency": "2 per year",
                        "ageLimit": "18"
                    }
                },
                "Exam": {
                    "value": {
                        "frequency": "every 6 months", 
                        "ageLimit": ""
                    }
                }
            }
        }
        
        OPENDENTAL MAPPING:
        - unit=1 (Months): Creates QuantityQualifier="Months", TimePeriod="None"
        - unit=2 (Years): Creates QuantityQualifier="Years", TimePeriod="None"  
        - unit=3 (Per Year): Creates QuantityQualifier="NumberOfServices", TimePeriod=plan_wide_time_period
        
        Returns:
        - Tuple[int, int]: (unit, frequency) where:
          - unit: 1=Months, 2=Years, 3=Per Year (NumberOfServices)
          - frequency: numeric value
        - Returns (0, 0) if parsing fails
        """
        if not frequency_str:
            return (0, 0)
            
        # Normalize the string
        normalized = str(frequency_str).lower().strip()
        
        # Handle special cases first
        special_cases = {
            'annually': (3, 1),
            'yearly': (3, 1),
            'biannually': (3, 2),
            'semiannually': (3, 2),
            'twice yearly': (3, 2),
            'twice per year': (3, 2),
            'once per year': (3, 1),
            'once yearly': (3, 1),
            'monthly': (1, 1),
            'quarterly': (1, 3),
            'semi-annually': (3, 2),
            'every year': (2, 1),  # Once every year
            'every month': (1, 1),  # Once every month
        }
        
        if normalized in special_cases:
            unit, freq = special_cases[normalized]
            log(f"Parsed special case '{frequency_str}' as unit={unit}, frequency={freq}")
            return (unit, freq)
        
        # Handle word-to-number conversion
        word_to_number = {
            'once': 1, 'one': 1, 'twice': 2, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12
        }
        
        # Replace word numbers with digits
        for word, number in word_to_number.items():
            normalized = re.sub(r'\b' + word + r'\b', str(number), normalized)
        
        # Pattern for "per X months/years" or "per month/year"
        # Examples: "per 3 months", "per month", "per year"
        leading_per_pattern = r'per\s+(?:(\d+(?:\.\d+)?)\s+)?(month|year|yr)s?'
        match = re.search(leading_per_pattern, normalized)
        if match:
            time_count_str = match.group(1)
            time_unit = match.group(2).strip() # Ensure no extra spaces in unit

            time_count = float(time_count_str) if time_count_str else 1.0 # Default to 1 if no number specified

            if time_unit in ['year', 'yr']:
                # "per year" -> every 1 year; "per X years" -> every X years
                unit, freq = (2, int(time_count))
            else: # month
                # "per month" -> every 1 month; "per X months" -> every X months
                unit, freq = (1, int(time_count))
            
            log(f"Parsed 'leading per' pattern '{frequency_str}' as unit={unit}, frequency={freq}")
            return (unit, freq)

        # Pattern 1: "X per Y months/years" or "X per year"
        per_pattern = r'(\d+(?:\.\d+)?)\s*per\s*(?:(\d+(?:\.\d+)?)\s*)?(month|year|yr)s?'
        match = re.search(per_pattern, normalized)
        if match:
            services_count = float(match.group(1))
            time_count = float(match.group(2)) if match.group(2) else 1
            time_unit = match.group(3)
            
            if time_unit in ['year', 'yr']:
                if time_count == 1:
                    # X per year -> NumberOfServices per year
                    unit, freq = (3, int(services_count))
                else:
                    # X per Y years -> once every (Y/X) years
                    unit, freq = (2, int(time_count / services_count)) if services_count > 0 else (2, int(time_count))
            else:  # months
                if time_count == 1 and services_count == 1:
                    # 1 per month -> once every 1 month
                    unit, freq = (1, 1)
                else:
                    # X per Y months -> once every (Y/X) months
                    unit, freq = (1, int(time_count / services_count)) if services_count > 0 else (1, int(time_count))
            
            log(f"Parsed 'per' pattern '{frequency_str}' as unit={unit}, frequency={freq}")
            return (unit, freq)
        
        # Pattern 2: "every X months/years" or "X months/years"
        every_pattern = r'(?:every\s+)?(\d+(?:\.\d+)?)\s*(month|year|yr)s?'
        match = re.search(every_pattern, normalized)
        if match:
            time_count = float(match.group(1))
            time_unit = match.group(2)
            
            if time_unit in ['year', 'yr']:
                unit, freq = (2, int(time_count))  # Every X years
            else:
                unit, freq = (1, int(time_count))  # Every X months
            
            log(f"Parsed 'every/time' pattern '{frequency_str}' as unit={unit}, frequency={freq}")
            return (unit, freq)
        
        # Pattern 3: Just a number (assume per year)
        number_only_pattern = r'^(\d+(?:\.\d+)?)$'
        match = re.search(number_only_pattern, normalized)
        if match:
            services_count = float(match.group(1))
            unit, freq = (3, int(services_count))  # X per year
            log(f"Parsed number-only '{frequency_str}' as unit={unit}, frequency={freq} (assumed per year)")
            return (unit, freq)
        
        # Pattern 4: "X times per year"
        times_pattern = r'(\d+(?:\.\d+)?)\s*times?\s*per\s*year'
        match = re.search(times_pattern, normalized)
        if match:
            services_count = float(match.group(1))
            unit, freq = (3, int(services_count))
            log(f"Parsed 'times per year' pattern '{frequency_str}' as unit={unit}, frequency={freq}")
            return (unit, freq)
        
        log(f"Warning: Could not parse frequency string '{frequency_str}'. Returning (0, 0)")
        return (0, 0)