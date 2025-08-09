from typing import Dict, List, Any, Optional, TypedDict, Union, TYPE_CHECKING
from dataclasses import dataclass
import re
import requests
import logging
import aiohttp
import asyncio
import time
from backend.logging_config import get_logger, LOG_INFO, LOG_ERROR, LOG_WARNING, LOG_SUCCESS

# Conditional import for type hinting to avoid circular dependency
if TYPE_CHECKING:
    pass  # Remove the incorrect import

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@dataclass
class FeeData:
    """Data class for fee information with explicit types"""
    code: str
    description: str
    amount: int

class FeeScheduleInput(TypedDict):
    """TypedDict for fee schedule input to ensure proper typing"""
    name: str
    type: str
    fees: List[Dict[str, str]]

class Result:
    """Result class for consistent API responses"""
    def __init__(self, success: bool, data: Any = None, error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self):
        """Convert result to dictionary format for API response"""
        if self.success:
            return {"ok": True, "value": self.data}
        return {"ok": False, "error": self.error}

def Ok(data): return Result(True, data).to_dict()
def Err(error): return Result(False, error=error).to_dict()

class FeeScheduleManager:
    """Manager class for fee schedule operations with OpenDental API"""
    # Valid fee schedule types
    FEE_SCHEDULE_TYPES = {
        'normal': 'Normal',
        'copay': 'CoPay',
        'outnetwork': 'OutNetwork',
        'fixedbenefit': 'FixedBenefit',
        'manualbluebook': 'ManualBlueBook'
    }

    @classmethod
    def create(cls, base_url=None, auth_token=None, pms_data=None):
        """Create a new instance of FeeScheduleManager"""
        instance = cls(base_url, auth_token, pms_data)
        instance._initialize_fee_schedules()
        return instance

    def __init__(self, base_url=None, auth_token=None, pms_data=None):
        """Initialize FeeScheduleManager with OpenDental connection details"""
        if not base_url:
            raise ValueError("OpenDental API URL is required")
        if not auth_token:
            raise ValueError("OpenDental auth token is required")
            
        # Ensure URL has protocol
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"https://{base_url}"
            
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.headers = {
            'Authorization': self.auth_token,
            'Content-Type': 'application/json'
        }
        
        # Store PMS data for procedure code lookups
        self.pms_data = pms_data or {}
        
        # Initialize collections
        self.fee_schedules = {}
        self.procedure_codes = {}
        self.api_responses = [] # Initialize list to store API call details
        
        # Load initial data
        self._initialize_mappings()
        
        logger.info("FeeScheduleManager initialized successfully")

    def make_request(self, endpoint: str, method: str = 'GET', data: Optional[dict] = None) -> Any:
        """Makes a request to the OpenDental API with error handling."""
        full_url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = None
            if method == 'GET':
                response = requests.get(full_url, headers=self.headers, timeout=30)
            elif method == 'POST':
                response = requests.post(full_url, headers=self.headers, json=data, timeout=30)
            elif method == 'PUT':
                response = requests.put(full_url, headers=self.headers, json=data, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            log_entry = {
                'timestamp': time.time(), 
                'method': method, 
                'url': full_url,
                'request_payload': data, 
                'status_code': response.status_code,
                'response_body': response.text  # Store raw text initially
            }
            
            if not response.ok:
                error_text = response.text
                logger.error(f"API error: {response.status_code} - {error_text} for {method} {full_url}")
                self.api_responses.append(log_entry)
                raise Exception(f"OpenDental API error: {response.status_code} - {error_text}")

            response_content = None
            if method == 'PUT' and (not response.content or response.text.strip() == ""):
                logger.info(f"PUT to {full_url} successful with empty/whitespace body. Amount: {data.get('Amount') if data else 'N/A'}.")
                response_content = {"_synthetic_put_ok": True, "Amount": data.get("Amount") if data else None}
            else:
                try:
                    response_content = response.json()
                    log_entry['response_body'] = response_content  # Update log with parsed JSON
                except requests.exceptions.JSONDecodeError as e_json:
                    logger.error(f"{method} to {full_url} successful (status {response.status_code}) but response body is not valid JSON. Content: '{response.text[:200]}...'. Error: {e_json}")
                    self.api_responses.append(log_entry)
                    raise Exception(f"OpenDental API success status {response.status_code} but sent non-JSON content for {method} {full_url}: {response.text[:200]}")
            
            self.api_responses.append(log_entry)
            return response_content

        except requests.RequestException as req_error:
            logger.error(f"Error in {method} request to {endpoint}: {str(req_error)}")
            self.api_responses.append({
                'timestamp': time.time(), 
                'method': method, 
                'url': full_url,
                'request_payload': data, 
                'status_code': 'REQUEST_EXCEPTION',
                'response_body': str(req_error)
            })
            raise 
        except Exception as generic_error: 
            logger.error(f"Unexpected error in {method} request to {endpoint}: {str(generic_error)}")
            self.api_responses.append({
                'timestamp': time.time(), 
                'method': method, 
                'url': full_url,
                'request_payload': data, 
                'status_code': 'UNEXPECTED_ERROR',
                'response_body': str(generic_error)
            })
            raise

    async def async_make_request(self, session: aiohttp.ClientSession, endpoint: str, method: str = 'GET', data: Optional[dict] = None) -> Any:
        """Makes an asynchronous request to the OpenDental API with error handling"""
        full_url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            logger.debug(f"Making async {method} request to {full_url}" + (f" with data: {data}" if data else ""))
            
            if method == 'GET':
                async with session.get(full_url, headers=self.headers, timeout=30) as response:
                    response.raise_for_status() 
                    return await response.json()
            elif method == 'POST':
                async with session.post(full_url, headers=self.headers, json=data, timeout=60) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method == 'PUT':
                async with session.put(full_url, headers=self.headers, json=data, timeout=60) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except aiohttp.ClientResponseError as error:
            error_text = await error.response.text() if error.response else "No response text"
            logger.error(f"API error: {error.status} - {error_text} for async {method} {full_url}")
            raise Exception(f"OpenDental API error: {error.status} - {error_text}")
        except aiohttp.ClientError as error: 
            logger.error(f"Client error in async {method} request to {endpoint}: {str(error)}")
            raise
        except Exception as error:
            logger.error(f"Unexpected error in async {method} request to {endpoint}. Error type: {type(error)}, repr: {repr(error)}, str: {str(error)}")
            # Attempt to log response details if available
            if hasattr(error, 'response') and error.response is not None:
                try:
                    status_code = error.response.status
                    # response_text = await error.response.text() # This might fail if response is already read or not text
                    logger.error(f"Associated response status (if any): {status_code}") #, text: {response_text[:500]}")
                except Exception as e_resp:
                    logger.error(f"Could not get details from error.response: {e_resp}")
            
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _format_amount_for_api(self, amount_input: Any) -> str:
        """Converts amount to string with 2 decimal places for API."""
        if amount_input is None:
            raise ValueError("Amount input cannot be None")
        try:
            # Remove currency symbols and commas, then convert to float
            amount_str_cleaned = str(amount_input).replace('$', '').replace(',', '')
            amount_float = float(amount_str_cleaned)
            # Format as string with 2 decimal places
            return f"{amount_float:.2f}"
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid amount format: {amount_input}. Error: {str(e)}") from e

    def _initialize_mappings(self):
        """Initialize procedure code mappings from PMS data"""
        try:   
            procedure_codes = self.pms_data['procedureCodes']
                
            # Map all procedure codes to their numbers
            for code, code_num in procedure_codes.items():
                if isinstance(code_num, (int, str)):
                    # Store the code and its number
                    self.procedure_codes[code] = {
                        'code_num': int(code_num),
                        'description': code
                    }
                    # Store the code number as a key for reverse lookup
                    self.procedure_codes[str(code_num)] = {
                        'code_num': int(code_num),
                        'description': code
                    }
        except Exception as e:
            print(f"Error initializing procedure code mappings: {str(e)}")

    def _initialize_fee_schedules(self):
        """Load existing fee schedules from the PMS"""
        try:
            # Get all fee schedules from the API
            response = self.make_request('/feescheds', method='GET')
            for fee_sched in response:
                name = fee_sched['Description'].lower()
                self.fee_schedules[name] = {
                    'id': fee_sched['FeeSchedNum'],
                    'type': fee_sched['FeeSchedType'],
                    'is_hidden': fee_sched['IsHidden'],
                    'is_global': fee_sched['IsGlobal']
                }
            
            logger.info(f"Loaded {len(self.fee_schedules)} fee schedules from OpenDental")
        except Exception as e:
            logger.error(f"Error loading fee schedules: {str(e)}")

    def _normalize_fee_schedule_name(self, name: str) -> str:
        """Normalize fee schedule name for consistent matching"""
        if not name:
            return ""
            
        # Convert to lowercase and remove special characters
        normalized = re.sub(r'[^a-z0-9]', ' ', name.lower())
        
        # Remove common words that don't affect matching
        common_words = [
            'fee', 'schedule', 'fees', 'insurance', 'ins', 
            'company', 'co', 'corp', 'corporation',
            'incorporated', 'inc',
            'dental', 'health', 'life',
            'of', 'the', 'and',
            'group', 'services',
            'limited', 'ltd'
        ]
        
        pattern = r'\b(' + '|'.join(common_words) + r')\b'
        normalized = re.sub(pattern, '', normalized)
        
        # Clean up extra spaces
        return ' '.join(normalized.split())
    
    def _get_or_create_fee_schedule(self, name: str, fee_schedule_type: str) -> Dict:
        """Get existing fee schedule or create new one"""
        try:
            normalized_name = self._normalize_fee_schedule_name(name)
            
            # Check if fee schedule exists by normalized name (self.fee_schedules should be populated by _initialize_fee_schedules)
            for sched_name_key, sched_data_val in self.fee_schedules.items(): # Iterate over items for clarity
                if self._normalize_fee_schedule_name(sched_name_key) == normalized_name:
                    logger.info(f"Found existing fee schedule for '{name}' (normalized: '{normalized_name}') with ID {sched_data_val['id']}")
                    return Ok({
                        "fee_sched_num": sched_data_val['id'],
                        "is_new": False
                    })

            # Create new fee schedule - use proper type format
            fee_type = self.FEE_SCHEDULE_TYPES.get(
                fee_schedule_type.lower(), 
                'Normal'
            )
            
            logger.info(f"Creating new fee schedule '{name}' with type '{fee_type}'")
            
            response = self.make_request('/feescheds', 'POST', data={
                "Description": name,
                "FeeSchedType": fee_type,
                "IsHidden": "false",
                "IsGlobal": "true"
            })
            
            # Extract fee schedule number from response
            fee_sched_num = response['FeeSchedNum']
            
            # Update local cache
            self.fee_schedules[normalized_name] = {
                'id': fee_sched_num,
                'type': fee_type,
                'is_hidden': "false",
                'is_global': "true"
            }
            
            logger.info(f"Created new fee schedule '{name}' with ID {fee_sched_num} of type '{fee_type}'")
            
            return Ok({
                "fee_sched_num": fee_sched_num,
                "is_new": True
            })
            
        except Exception as error:
            logger.error(f"Error in fee schedule creation: {str(error)}")
            return Err(f"Failed to create fee schedule: {str(error)}")

    def _get_code_num(self, procedure_code: str) -> int:
        """Get CodeNum for a given procedure code from PMS data"""
        try:            
            # Check our local cache
            if procedure_code in self.procedure_codes:
                code_num = self.procedure_codes[procedure_code]['code_num']
                if code_num:
                    return code_num
            
            return 0
            
        except Exception as e:
            return 0

    def setup_fee_schedule(self, fee_schedule_data: FeeScheduleInput) -> Dict:
        """Set up a fee schedule with fees in OpenDental, synchronously processing fees with throttling."""
        try:
            name = fee_schedule_data.get('name')
            fee_schedule_type_input = fee_schedule_data.get('type', 'Normal')
            if fee_schedule_type_input.lower() == 'standard':
                 fee_schedule_type_input = 'Normal'
            fees = fee_schedule_data.get('fees', [])

            if not name or not isinstance(name, str) or not name.strip():
                return Err("Missing or invalid required field: name must be a non-empty string")
            if not fees or not isinstance(fees, list): 
                 return Err("Missing or invalid required field: fees must be a list")

            logger.info(f"Setting up fee schedule '{name}' with {len(fees)} fees.")
            
            fee_schedule_result = self._get_or_create_fee_schedule(name, fee_schedule_type_input)
            if not fee_schedule_result.get('ok', False):
                return Err(f"Failed to get/create fee schedule: {fee_schedule_result.get('error')}")
            
            fee_sched_num_val = fee_schedule_result.get('value', {})
            fee_sched_num_str = fee_sched_num_val.get('fee_sched_num')
            is_new = fee_sched_num_val.get('is_new', False)
            
            if not is_new:
                logger.warning(f"Attempt to create a new fee schedule '{name}', but an existing one was found with ID {fee_sched_num_str}. Instructing user to update.")
                return Err(f"A fee schedule with the name '{name}' already exists. Please use the update functionality instead.")

            if not fee_sched_num_str:
                return Err("Failed to get fee schedule number")
            
            try:
                fee_sched_num_int = int(fee_sched_num_str)
            except ValueError:
                logger.error(f"Invalid FeeSchedNum format: {fee_sched_num_str}")
                return Err(f"Invalid fee schedule number format: {fee_sched_num_str}")

            successful_fees = 0
            failed_fees = 0

            if not fees:
                logger.info(f"No fees provided for fee schedule '{name}' (ID: {fee_sched_num_int}). Skipping fee processing.")
            else:
                total_fees_to_process = len(fees)
                processed_count = 0
                logger.info(f"Processing {total_fees_to_process} fees for new fee schedule '{name}' (ID: {fee_sched_num_int}) with 0.5 req/sec throttle.")
                
                for fee_input in fees:
                    processed_count += 1
                    code = str(fee_input.get('code', '')).strip()
                    amount_input = fee_input.get('amount')
                    status_msg = ""
                    current_code_num = None 

                    try:
                        if not code or amount_input is None:
                            logger.warning(f"Skipping fee {processed_count}/{total_fees_to_process} for schedule '{name}' (ID: {fee_sched_num_int}) due to missing code or amount: {fee_input}")
                            failed_fees += 1
                            continue
                        
                        amount_str = self._format_amount_for_api(amount_input)
                        api_response_ok = False
                        
                        current_code_num = self._get_code_num(code)
                        if not current_code_num:
                            logger.warning(f"Could not find CodeNum for procedure code '{code}' for schedule '{name}' (ID: {fee_sched_num_int}). Skipping fee {processed_count}/{total_fees_to_process}.")
                            failed_fees += 1
                            continue

                        create_payload = {
                            "Amount": amount_str,
                            "FeeSched": fee_sched_num_int,
                            "CodeNum": current_code_num
                        }
                        response = self.make_request('/fees', 'POST', data=create_payload)
                        if response and 'FeeNum' in response:
                            status_msg = 'Created'
                            api_response_ok = True
                        else:
                            logger.error(f"Failed to create new fee for CodeNum {current_code_num} on schedule '{name}' (ID: {fee_sched_num_int}) - invalid API response: {response}")
                        
                        if api_response_ok:
                            successful_fees += 1
                            logger.info(f"Fee {processed_count}/{total_fees_to_process} for '{name}' (ID: {fee_sched_num_int}, Code: {code}, CodeNum: {current_code_num}): {status_msg} with Amount: {amount_str}")
                        else:
                            if not status_msg: 
                                logger.error(f"Fee processing failed for Code {code} (CodeNum {current_code_num}) on schedule '{name}' (ID: {fee_sched_num_int}). Action not taken.")
                            failed_fees += 1
                            
                    except ValueError as ve: 
                        logger.error(f"Failed to process fee {processed_count}/{total_fees_to_process} for schedule '{name}' (ID: {fee_sched_num_int}, Code: {code}). Error: Invalid value - {str(ve)}")
                        failed_fees += 1
                    except Exception as e_api: 
                        logger.error(f"Failed to process fee {processed_count}/{total_fees_to_process} for schedule '{name}' (ID: {fee_sched_num_int}, Code: {code}, CodeNum: {current_code_num if current_code_num is not None else 'N/A'}). API Error: {str(e_api)}")
                        failed_fees += 1
                    
                    time.sleep(0.5) # Throttle
            
            return Ok({
                "fee_sched_num": fee_sched_num_str,
                "is_new": is_new, 
                "successful_fees": successful_fees,
                "failed_fees": failed_fees,
            })
            
        except Exception as e:
            logger.exception(f"General error in setup_fee_schedule for '{name if 'name' in locals() else 'unknown'}': {str(e)}")
            return Err(f"Failed to set up fee schedule: {str(e)}")

    def update_fee_schedule(self, fee_sched_num_str: str, name: Optional[str] = None, 
                                fee_sched_type: Optional[str] = None, 
                                fees: Optional[List[Dict]] = None) -> Dict:
        """
        Update an existing fee schedule name (if provided) and its fees synchronously with throttling.
        """
        try:
            if not fee_sched_num_str:
                return Err("Fee schedule number is required")

            try:
                fee_sched_num_int = int(fee_sched_num_str) 
            except (ValueError, TypeError):
                return Err(f"Invalid fee schedule number: {fee_sched_num_str}")

            logger.info(f"Updating fee schedule '{fee_sched_num_str}'.")

            name_updated_successfully = False
            if name:
                try:
                    logger.info(f"Updating fee schedule {fee_sched_num_int} name to '{name}'")
                    current_schedule_data_response = self.make_request(f"/feescheds/{fee_sched_num_int}", method='GET')
                    actual_schedule_details = None
                    if isinstance(current_schedule_data_response, list):
                        if current_schedule_data_response:
                            actual_schedule_details = current_schedule_data_response[0]
                    elif isinstance(current_schedule_data_response, dict):
                        actual_schedule_details = current_schedule_data_response

                    if not actual_schedule_details:
                        return Err(f"Could not retrieve current details for fee schedule {fee_sched_num_int} to update name.")

                    name_update_payload = {
                        "Description": name,
                    }
                    if fee_sched_type and actual_schedule_details.get("FeeSchedType") != self.FEE_SCHEDULE_TYPES.get(fee_sched_type.lower()):
                         logger.warning(f"FeeSchedType cannot be changed for existing FeeSched {fee_sched_num_int}. Ignoring new type '{fee_sched_type}'. Current type: {actual_schedule_details.get('FeeSchedType')}")

                    name_update_response = self.make_request(
                        f"/feescheds/{fee_sched_num_int}", 
                        'PUT',
                        data=name_update_payload
                    )
                    if name_update_response and (name_update_response.get('FeeSchedNum') or name_update_response.get('_synthetic_put_ok')):
                        name_updated_successfully = True
                        logger.info(f"Successfully updated name for fee schedule {fee_sched_num_int}")
                        for fs_name_cache, fs_data_cache in list(self.fee_schedules.items()):
                            if fs_data_cache.get('id') == fee_sched_num_int:
                                del self.fee_schedules[fs_name_cache]
                                self.fee_schedules[name.lower()] = fs_data_cache 
                                break
                    else:
                        logger.error(f"Failed to update fee schedule name for {fee_sched_num_int}. Response: {name_update_response}")

                except Exception as name_error:
                    logger.error(f"Error updating fee schedule name for {fee_sched_num_int}: {str(name_error)}")
                    
            successful_fees_processed = 0
            failed_fees_processed = 0
            
            if fees and isinstance(fees, list):
                logger.info(f"Fetching existing fees for schedule {fee_sched_num_int} before update using pagination.")
                existing_fees_map = {} 
                all_fetched_fees_list = [] 
                offset = 0
                BATCH_SIZE = 100 
                has_more_data = True

                while has_more_data:
                    try:
                        logger.debug(f"Fetching fees for schedule {fee_sched_num_int} with offset {offset}")
                        paginated_endpoint = f"/fees?FeeSched={fee_sched_num_int}&Offset={offset}"
                        current_batch_fees_data = self.make_request(paginated_endpoint, method='GET')
                        
                        if isinstance(current_batch_fees_data, list):
                            all_fetched_fees_list.extend(current_batch_fees_data)
                            logger.debug(f"Fetched {len(current_batch_fees_data)} fees in this batch for schedule {fee_sched_num_int}.")
                            if len(current_batch_fees_data) < BATCH_SIZE:
                                has_more_data = False 
                            else:
                                offset += BATCH_SIZE
                        else:
                            logger.error(f"Unexpected response type when fetching fees for schedule {fee_sched_num_int} at offset {offset}. Response: {current_batch_fees_data}")
                            has_more_data = False 

                    except Exception as e_fetch_batch:
                        logger.error(f"Error fetching fees batch for schedule {fee_sched_num_int} at offset {offset}: {str(e_fetch_batch)}")
                        has_more_data = False 
                
                if all_fetched_fees_list:
                    for fee_item in all_fetched_fees_list:
                        if isinstance(fee_item, dict) and 'CodeNum' in fee_item and 'FeeNum' in fee_item and 'Amount' in fee_item:
                            existing_fees_map[fee_item['CodeNum']] = fee_item 
                
                logger.info(f"Found a total of {len(existing_fees_map)} existing fees for schedule {fee_sched_num_int} after pagination.")
                
                total_fees_to_process = len(fees)
                processed_count = 0
                logger.info(f"Processing {total_fees_to_process} fee updates synchronously for schedule {fee_sched_num_int} with 0.5 req/sec throttle.")
                
                for fee_input in fees:
                    processed_count += 1
                    code = str(fee_input.get('code', '')).strip()
                    amount_input = fee_input.get('amount')
                    status_msg = ""
                    current_code_num = None 

                    try:
                        if not code or amount_input is None:
                            logger.warning(f"Skipping fee update {processed_count}/{total_fees_to_process} for schedule {fee_sched_num_int} due to missing code or amount: {fee_input}")
                            failed_fees_processed += 1
                            continue
                        
                        current_code_num = self._get_code_num(code)
                        if not current_code_num:
                            logger.warning(f"Could not find CodeNum for procedure code '{code}' for schedule {fee_sched_num_int}. Skipping fee update {processed_count}/{total_fees_to_process}.")
                            failed_fees_processed += 1
                            continue

                        amount_str_new = self._format_amount_for_api(amount_input)
                        api_response_ok = False
                        
                        if current_code_num in existing_fees_map:
                            existing_fee_details = existing_fees_map[current_code_num]
                            existing_amount_formatted = f"{float(existing_fee_details['Amount']):.2f}" # Format existing amount for comparison

                            if amount_str_new == existing_amount_formatted:
                                logger.info(f"Fee {processed_count}/{total_fees_to_process} for schedule {fee_sched_num_int} (Code: {code}, CodeNum: {current_code_num}): Amount ${amount_str_new} matches existing amount. Skipping update.")
                                successful_fees_processed +=1 # Count as success as it's already correct
                                continue # Skip API call

                            fee_num = existing_fee_details['FeeNum']
                            update_payload = {"Amount": amount_str_new}
                            
                            response = self.make_request(f'/fees/{fee_num}', 'PUT', data=update_payload)
                            if response and (response.get('FeeNum') or response.get('_synthetic_put_ok')):
                                status_msg = 'Updated'
                                api_response_ok = True
                            else:
                                logger.error(f"Failed to update fee for CodeNum {current_code_num} on schedule {fee_sched_num_int} - invalid API response: {response}")
                        else:
                            create_payload = {
                                "Amount": amount_str_new,
                                "FeeSched": fee_sched_num_int,
                                "CodeNum": current_code_num
                            }
                            response = self.make_request('/fees', 'POST', data=create_payload)
                            if response and 'FeeNum' in response: 
                                status_msg = 'Created'
                                api_response_ok = True
                            else:
                                logger.error(f"Failed to create new fee for CodeNum {current_code_num} on schedule {fee_sched_num_int} - invalid API response: {response}")

                        if api_response_ok:
                            successful_fees_processed += 1
                            logger.info(f"Fee {processed_count}/{total_fees_to_process} for schedule {fee_sched_num_int} (Code: {code}, CodeNum: {current_code_num}): {status_msg} with Amount: {amount_str_new}")
                        else:
                            if not status_msg: 
                                logger.error(f"Fee processing failed for Code {code} (CodeNum {current_code_num}) on schedule {fee_sched_num_int} (not updated or created).")
                            failed_fees_processed += 1
                            
                    except ValueError as ve: 
                        logger.error(f"Failed to process fee {processed_count}/{total_fees_to_process} for schedule {fee_sched_num_int} (Code: {code}). Error: Invalid value - {str(ve)}")
                        failed_fees_processed += 1
                    except Exception as e_api: 
                        logger.error(f"Failed to process fee {processed_count}/{total_fees_to_process} for schedule {fee_sched_num_int} (Code: {code}, CodeNum: {current_code_num if current_code_num is not None else 'N/A'}). API Error: {str(e_api)}")
                        failed_fees_processed += 1
                    
                    time.sleep(0.5) 

            return Ok({
                "message": "Fee schedule update process completed.",
                "data": {
                    "feeSchedNum": fee_sched_num_str,
                    "nameUpdated": name_updated_successfully,
                    "updatedFees": successful_fees_processed,
                    "failedFees": failed_fees_processed
                }
            })
            
        except Exception as error:
            logger.exception(f"General error in update_fee_schedule for '{fee_sched_num_str}': {str(error)}")
            return Err(f"Failed to update fee schedule {fee_sched_num_str}: {str(error)}")

    def hide_fee_schedule(self, fee_sched_num: str, description: Optional[str] = None) -> Dict:
        """
        Hide a fee schedule in OpenDental
        
        Args:
            fee_sched_num: The fee schedule number to hide
            description: The name/description of the fee schedule
            
        Returns:
            Dictionary with operation result
        """
        try:
            if not fee_sched_num:
                return Err("Fee schedule number is required")
                
            # Convert fee_sched_num to integer
            try:
                fee_sched_num_int = int(fee_sched_num)
            except (ValueError, TypeError):
                return Err(f"Invalid fee schedule number: {fee_sched_num}")
            
            # If description not provided, try to find it in our local cache
            if not description:
                for name, data in self.fee_schedules.items():
                    if data.get('id') == fee_sched_num_int:
                        description = name
                        break
                        
                # If still not found, try getting it directly from the API
                if not description:
                    try:
                        schedule_info = self.make_request(f"/feescheds/{fee_sched_num_int}", method='GET')
                        if schedule_info:
                            description = schedule_info.get('Description')
                    except Exception as e:
                        logger.warning(f"Could not get fee schedule info: {str(e)}")
            
            # Prepare payload for API call - MUST include Description as per API docs
            payload = {"IsHidden": "true"}
            if description:
                payload["Description"] = description
                logger.info(f"Hiding fee schedule {fee_sched_num} with description '{description}'")
            else:
                logger.warning(f"No description found for fee schedule {fee_sched_num}")
                # Still need to include a Description even if we don't have it
                payload["Description"] = f"Schedule {fee_sched_num}"
                
            hide_result = self.make_request(
                f"/feescheds/{fee_sched_num_int}", 
                'PUT', 
                data=payload
            )
            
            if not hide_result:
                return Err("Failed to hide fee schedule")
                
            # Update local cache
            for name, data in list(self.fee_schedules.items()):
                if data.get('id') == fee_sched_num_int:
                    data['is_hidden'] = "true"
                    break
                    
            return Ok({
                "message": "Fee schedule hidden successfully",
                "data": {
                    "feeSchedNum": fee_sched_num
                }
            })
            
        except Exception as error:
            logger.error(f"Error hiding fee schedule: {str(error)}")
            return Err(f"Failed to hide fee schedule: {str(error)}")

    def update_ins_plan_fee_schedule(self, ins_plan_num: str, fee_sched_num_to_attach: Union[str, int]) -> Dict:
        """
        Updates an existing insurance plan to attach a specific fee schedule.
        Only updates the FeeSched field of the insurance plan.

        Args:
            ins_plan_num: The PlanNum of the insurance plan to update.
            fee_sched_num_to_attach: The FeeSchedNum of the fee schedule to attach.

        Returns:
            Dictionary with operation result.
        """
        try:
            if not ins_plan_num:
                return Err("Insurance Plan Number (ins_plan_num) is required.")
            if fee_sched_num_to_attach is None: # Allow 0 as a valid FeeSchedNum
                return Err("Fee Schedule Number to attach (fee_sched_num_to_attach) is required.")

            try:
                # The FeeSched field in InsPlans PUT expects an integer.
                fee_sched_id = int(fee_sched_num_to_attach)
            except ValueError:
                logger.error(f"Invalid FeeSchedNum format for attachment: {fee_sched_num_to_attach}")
                return Err(f"Invalid Fee Schedule Number format for attachment: {fee_sched_num_to_attach}")

            payload = {"FeeSched": fee_sched_id}
            endpoint = f"/insplans/{ins_plan_num}"
            
            logger.info(f"Attempting to update InsPlan {ins_plan_num} with FeeSched: {fee_sched_id}")
            
            response = self.make_request(endpoint, 'PUT', data=payload)
            
            # According to InsPlans PUT documentation, a successful response returns the updated InsPlan object.
            # We can check for a key that's expected in the response, e.g., "PlanNum".
            if response and response.get("PlanNum") is not None:
                logger.info(f"Successfully updated InsPlan {ins_plan_num} to use FeeSched {fee_sched_id}. Response: {response}")
                return Ok({
                    "message": f"Insurance Plan {ins_plan_num} successfully updated to use Fee Schedule {fee_sched_id}.",
                    "data": response 
                })
            else:
                logger.error(f"Failed to update InsPlan {ins_plan_num}. Response: {response}")
                # Try to extract a more specific error if available from OpenDental's typical error structure
                error_detail = "Unknown error or unexpected response structure."
                if isinstance(response, dict):
                    error_detail = response.get("error", response.get("Message", error_detail))

                return Err(f"Failed to update Insurance Plan {ins_plan_num}: {error_detail}")

        except Exception as e:
            logger.exception(f"Error updating InsPlan {ins_plan_num} with FeeSched {fee_sched_num_to_attach}: {str(e)}")
            return Err(f"An unexpected error occurred while updating InsPlan {ins_plan_num}: {str(e)}")

    def get_api_responses(self) -> List[Dict[str, Any]]:
        """Retrieve all API responses collected during the manager's lifecycle."""
        return self.api_responses