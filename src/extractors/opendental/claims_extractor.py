#claimsOpenDental
from typing import TypedDict, Any, Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
import requests
import os
from dotenv import load_dotenv
import pytz
import time
import json
import logging
import paramiko

# Initialize logger
logger = logging.getLogger(__name__)

# Import from claimsMatching
from .claimsMatchingOpenDental import ClaimMatcher, SearchCriteria, ClaimMatch, ProcedurePayment, PaymentInfo

# print("Loading environment variables...")
load_dotenv()

class SFTPConfig(TypedDict):
    address: str
    username: str | None
    password: str | None
    incoming_dir: str
    processed_dir: str

class OpenDentalAPI:
    ######################################################################################
    # Constructor
    ######################################################################################

    def __init__(self, base_url=None, auth_token=None, pms_data=None, locationId=None):        
        if not base_url:
            raise ValueError("OpenDental API URL not found in location settings")
        if not auth_token:
            raise ValueError("OpenDental auth token not found in location settings")
            
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"https://{base_url}"
            
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.headers = {
            'Authorization': self.auth_token,
            'Content-Type': 'application/json'
        }
        self.pms_data = pms_data

        # Add a collection to store API responses
        self.api_responses = []

        # Initialize ClaimMatcher
        self.claim_matcher = ClaimMatcher(make_request_callable=self.make_request, pms_data=self.pms_data)

        # Fetch and cache ClaimPaymentTracking definitions on initialization
        self.claim_payment_tracking_defs = []
        try:
            logger.warning("Fetching ClaimPaymentTracking definitions...")
            self.claim_payment_tracking_defs = self.get_claim_payment_tracking_defs()
            logger.warning(f"Successfully fetched {len(self.claim_payment_tracking_defs)} ClaimPaymentTracking definitions.")
        except Exception as e:
            logger.warning(f"Error fetching ClaimPaymentTracking definitions during init: {e}")
            
        # Initialize carrier cache
        self._carrier_cache = {}
        self._carriers_fetched = False

    @staticmethod
    def _load_sftp_config() -> SFTPConfig:
        print(f"=== Load SFTP Credentials ===")
        print("[SFTP Config] Loading configuration")

        sftp_address = os.environ.get('SFTP_ADDRESS')
        sftp_username = os.environ.get('SFTP_USERNAME')
        sftp_password = os.environ.get('SFTP_PASSWORD')
        sftp_incoming_dir = os.environ.get('SFTP_INCOMING_DIR', 'incoming')
        sftp_processed_dir = os.environ.get('SFTP_PROCESSED_DIR', 'processed')

        print("[SFTP Config] Credentials check:")
        print(f"  Address found: {'Yes' if sftp_address else 'No'}")
        print(f"  Username found: {'Yes' if sftp_username else 'No'}")
        print(f"  Password found: {'Yes' if sftp_password else 'No'}")
        print(f"  Incoming Dir: {sftp_incoming_dir}")
        print(f"  Processed Dir: {sftp_processed_dir}")

        return {
            "address": sftp_address or "",
            "username": sftp_username or "",
            "password": sftp_password or "",
            "incoming_dir": sftp_incoming_dir.lstrip('/'),
            "processed_dir": sftp_processed_dir.lstrip('/'),
        }

    def make_request(self, endpoint: str, method: str = 'GET', data: Optional[dict] = None) -> dict:
        """Makes a request to the OpenDental API with retry capability"""
        full_url = f"{self.base_url}/{endpoint.lstrip('/')}"
        max_retries = 3
        retry_delay = 1  # Start with 1 second delay
        attempt = 0
        
        # Add a fixed delay before every request to prevent race conditions
        time.sleep(0.150) # 150ms delay
        
        while attempt < max_retries:
            try:
                timeout = 60 if endpoint == 'documents/Upload' else 30

                if method == 'GET':
                    response = requests.get(full_url, headers=self.headers, timeout=timeout)
                elif method == 'PUT':
                    response = requests.put(full_url, headers=self.headers, json=data, timeout=timeout)
                elif method == 'POST':
                    response = requests.post(full_url, headers=self.headers, json=data, timeout=timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                    
                if not response.ok:
                    raise Exception(f"OpenDental API error: {response.status_code} - {response.text}")
                
                # Store responses for PUT and POST operations
                if method in ['PUT', 'POST']:
                    response_data = {
                        'timestamp': datetime.now().isoformat(),
                        'method': method,
                        'endpoint': endpoint,
                        'request_data': data,
                        'status_code': response.status_code,
                        'response': response.json() if response.text else None
                    }
                    self.api_responses.append(response_data)
                    logger.warning(f"[API Response Tracker] Stored {method} response for {endpoint}")

                return response.json()
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as error:
                # Only retry connection errors and timeouts
                attempt += 1
                if attempt >= max_retries:
                    logger.error(f"Failed after {max_retries} attempts to {method} {endpoint}: {error}")
                    raise
                
                logger.warning(f"Connection error on attempt {attempt}/{max_retries} for {method} {endpoint}: {error}")
                logger.warning(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            except Exception as error:
                # Don't retry other errors
                logger.error(f"Error in {method} request to {endpoint}: {error}")
                raise
        
        # This should never be reached, but adding to satisfy the linter
        raise Exception(f"Failed to complete request after {max_retries} attempts")
    
    # Method to get ClaimPaymentTracking definitions
    def get_claim_payment_tracking_defs(self) -> List[Dict]:
        """Fetches ClaimPaymentTracking definitions (Category 36) from the API."""
        try:
            # Category 36 is for ClaimPaymentTracking
            definitions = self.make_request('definitions?Category=36')
            # Ensure it's a list before returning
            return definitions if isinstance(definitions, list) else []
        except Exception as e:
            logger.warning(f"Error fetching definitions (Category 36): {e}")
            return [] # Return empty list on error

    # Method to get collected API responses
    def get_api_responses(self):
        """Returns the collected API responses for PUT and POST operations"""
        return self.api_responses
    
    def get_carrier_name_from_claim(self, claim_data: dict) -> Optional[str]:
        """Get carrier name from a claim by looking up the insurance plan and carrier.
        
        Args:
            claim_data: The claim data dictionary containing PlanNum or PlanNum2
            
        Returns:
            The carrier name if found, None otherwise
        """
        try:
            # Step 1: Get the plan number (primary or secondary based on claim type)
            plan_num = None
            
            # Check if this is a secondary claim
            if claim_data.get('ClaimType') == 'S' and claim_data.get('PlanNum2'):
                plan_num = claim_data.get('PlanNum2')
                logger.info(f"Using secondary plan number: {plan_num}")
            elif claim_data.get('PlanNum'):
                plan_num = claim_data.get('PlanNum')
                logger.info(f"Using primary plan number: {plan_num}")
            else:
                logger.warning("No plan number found in claim data")
                return None
                
            # Step 2: Call /insplans/{planNum} to get the CarrierNum
            try:
                insplan = self.make_request(f"insplans/{plan_num}")
                carrier_num = insplan.get('CarrierNum')
                
                if not carrier_num:
                    logger.warning(f"No CarrierNum found in insplan {plan_num}")
                    return None
                    
                logger.info(f"Found CarrierNum {carrier_num} for plan {plan_num}")
                
            except Exception as e:
                logger.error(f"Error fetching insplan {plan_num}: {e}")
                return None
                
            # Step 3: Check if we have the carrier name in cache
            if carrier_num in self._carrier_cache:
                carrier_name = self._carrier_cache[carrier_num]
                logger.info(f"Found carrier name in cache: {carrier_name}")
                return carrier_name
                
            # Step 4: If not in cache and we haven't fetched all carriers yet, call /carriers/1
            if not self._carriers_fetched:
                try:
                    # Note: The API spec shows /carriers returns ALL carriers, not just one
                    all_carriers = self.make_request("carriers")
                    
                    # Step 6: Cache all carriers for future lookups
                    for carrier in all_carriers:
                        c_num = carrier.get('CarrierNum')
                        c_name = carrier.get('CarrierName')
                        if c_num and c_name:
                            self._carrier_cache[c_num] = c_name
                            
                    self._carriers_fetched = True
                    logger.info(f"Cached {len(self._carrier_cache)} carriers")
                    
                except Exception as e:
                    logger.error(f"Error fetching all carriers: {e}")
                    # Try to fetch individual carrier as fallback
                    try:
                        single_carrier = self.make_request(f"carriers/{carrier_num}")
                        carrier_name = single_carrier.get('CarrierName')
                        if carrier_name:
                            self._carrier_cache[carrier_num] = carrier_name
                            return carrier_name
                    except Exception as e2:
                        logger.error(f"Error fetching single carrier {carrier_num}: {e2}")
                        return None
                        
            # Step 5: Filter through the array to find the matching CarrierNum
            # (Already done in step 6 when caching)
            
            # Step 7: Return the carrier name
            if carrier_num in self._carrier_cache:
                carrier_name = self._carrier_cache[carrier_num]
                logger.info(f"Found carrier name after fetching: {carrier_name}")
                return carrier_name
            else:
                logger.warning(f"Carrier {carrier_num} not found in fetched carriers")
                return None
                
        except Exception as e:
            logger.error(f"Error in get_carrier_name_from_claim: {e}")
            return None

    def find_matching_claims(self, criteria: SearchCriteria, claims_data: Optional[Dict[str, Any]] = None, skip_api_fallback: bool = False) -> list[ClaimMatch]:
        """
        Find claims matching the search criteria.
        Uses ClaimMatcher for DB and API search logic.
        Attempts DB search first. If any claims are found (meeting DB search's internal score threshold),
        those are returned. Otherwise, falls back to API search for supplemental "Received" claims,
        unless skip_api_fallback is True.
        """
        log_prefix = f"[OD_API Claim Search: {criteria.patient_first_name} {criteria.patient_last_name}]"

        if claims_data:
            try:
                # Use ClaimMatcher for DB search (filter_cached_claims).
                logger.warning(f"{log_prefix} Attempting DB search using ClaimMatcher.filter_cached_claims...")
                db_matches = self.claim_matcher.filter_cached_claims(criteria, claims_data)
                
                if db_matches:  
                    logger.warning(f"{log_prefix} Found {len(db_matches)} match(es) in cached claims. Using these results.")
                    return db_matches 
                else:
                    if skip_api_fallback:
                        logger.warning(f"{log_prefix} No matches found in cached claims and skip_api_fallback is True. Returning empty list.")
                        return [] # Skip API fallback
                    logger.warning(f"{log_prefix} No matches found in cached claims. Proceeding with API fallback for 'Received' or 'Sent' claims.")
            except Exception as db_err:
                logger.warning(f"{log_prefix} Error during cached claims search: {db_err}. Falling back to API search for 'Received' or 'Sent' claims (unless skipped).")
                if skip_api_fallback:
                    logger.warning(f"{log_prefix} skip_api_fallback is True after DB error. Returning empty list.")
                    return [] # Skip API fallback
        else:
            if skip_api_fallback:
                logger.warning(f"{log_prefix} No cached claims_data provided and skip_api_fallback is True. Returning empty list.")
                return [] # Skip API fallback
            logger.warning(f"{log_prefix} No cached claims_data provided. Proceeding with API fallback for 'Received' or 'Sent' claims.")

        # Fallback to API search for "Received" or "Sent" claims using ClaimMatcher
        logger.warning(f"{log_prefix} INITIATING API FALLBACK SEARCH via ClaimMatcher.find_matching_claims_api_fallback... (skip_api_fallback={skip_api_fallback})")
        try:
            # This now calls the refactored ClaimMatcher.find_matching_claims_api_fallback which looks for "Received" or "Sent" claims.
            # Pass skip_api_fallback to the ClaimMatcher's method
            api_supplemental_matches = self.claim_matcher.find_matching_claims_api_fallback(criteria, skip_api_fallback=skip_api_fallback)
            
            # The isOrtho, ortho_details, and is_supplemental flags should already be set correctly by ClaimMatcher.
            # No need to explicitly set match_source here as ClaimMatcher methods handle it.
            if api_supplemental_matches:
                logger.warning(f"{log_prefix} Found {len(api_supplemental_matches)} supplemental match(es) via API fallback.")
            else:
                logger.warning(f"{log_prefix} No supplemental matches found via API fallback.")
            return api_supplemental_matches
        except Exception as api_err:
            logger.error(f"{log_prefix} Error during API fallback (supplemental) search: {api_err}")
            raise 

    def split_claim(self, claim_num: int, proc_nums: List[int]) -> Dict[str, Any]:
        """Split a claim into multiple claims
        
        Args:
            claim_num: The ID of the claim to split
            proc_nums: List of procedure numbers to move to the new claim
            
        Returns:
            Dict containing the new claim number and the moved procedure numbers
        """
        try:
            # Prepare the data for the split operation
            data = {
                "ProcNums": proc_nums
            }
            
            # Make the PUT request to split the claim
            result = self.make_request(f"claims/{claim_num}/Split", method='PUT', data=data)
            return result
        except Exception as e:
            logger.error(f"Error splitting claim {claim_num}: {e}")
            raise

    ######################################################################################
    # Finds Claim, updates amount paid, updates claim status, then finalizes claim
    ######################################################################################

    def process_claim_update(self, claim_num: int, payment_info: PaymentInfo) -> Dict[str, Any]:
        """Process full claim payment workflow"""
        try:
            # 1. Get ClaimProcs for the claim
            claim_procs = self.make_request(f"claimprocs?ClaimNum={claim_num}")
            logger.warning(f"=== Start Claims Payment Process ===")
            logger.warning(f"[Claim Update {claim_num}] Processing claim #{claim_num}")
            logger.warning(f"[Claim Update {claim_num}] Found {len(claim_procs)} claim procedures")
            total_paid = 0.0

            # 2. Update each ClaimProc
            for proc in claim_procs:
                # Find matching procedure payment
                proc_code = proc['CodeSent']
                proc_payment = next(
                    (p for p in payment_info.procedures if p.proc_code == proc_code),
                    None
                )
                
                if proc_payment:
                    update_data = {
                        "Status": "Received",
                        "InsPayAmt": proc_payment.amount_paid
                    }
                    # Add remarks to the update if available
                    if hasattr(proc_payment, 'remarks') and proc_payment.remarks:
                        update_data["Remarks"] = proc_payment.remarks
                    
                    update_response = self.make_request(
                        f"claimprocs/{proc['ClaimProcNum']}", 
                        method='PUT',
                        data=update_data
                    )
                    total_paid += proc_payment.amount_paid
                    # logger.warning(f"[Claims Payment] Running total paid: {total_paid}")
                else:
                    logger.warning(f"[Claim Update {claim_num}] No payment info found for proc code: {proc_code}")

            logger.warning(f"[Claim Update {claim_num}] Total paid amount: {total_paid}")

            # 3. Update claim status to "Received"
            update_claim_response = self.make_request(
                f"claims/{claim_num}",
                method='PUT',
                data={
                    "ClaimStatus": "R", # R = Received
                    "DateReceived": datetime.now(pytz.timezone('US/Mountain')).date().strftime('%Y-%m-%d')
                }
            )
            logger.warning(f"[Claim Update {claim_num}] Updated claim status to Received")

            # 4. Finalize the payment
            payment_response = self.make_request(
                "claimpayments",
                method='POST',
                data={
                    "claimNum": claim_num,
                    "CheckAmt": total_paid,
                    "CheckDate": datetime.now(pytz.timezone('US/Mountain')).date().strftime('%Y-%m-%d'),
                    "CheckNum": payment_info.check_number,
                    "CarrierName": payment_info.carrier_name if hasattr(payment_info, 'carrier_name') else None,
                    "DateIssued": payment_info.date_issued if hasattr(payment_info, 'date_issued') else None,
                    "BankBranch": payment_info.bank_branch if hasattr(payment_info, 'bank_branch') else None,
                    "Note": payment_info.note if hasattr(payment_info, 'note') else None
                }
            )
            
            logger.warning(f"[Claim Update {claim_num}] Finalized payment. Response: {payment_response}")
            logger.warning(f"================================\n")

            return {"success": True, "claim_num": claim_num, "payment_response": payment_response}
        except Exception as e:
            logger.error(f"Error processing claim update for claim #{claim_num}: {str(e)}")
            return {"success": False, "error": str(e)}

    def process_eob_matching(self, criteria: SearchCriteria) -> Dict[str, Any]:
        """Process EOB matching and payment"""
        try:
            # Find matching claims
            matching_claims = self.find_matching_claims(criteria)
            if not matching_claims:
                return {"success": False, "message": "No matching claims found"}
            
            # Extract claim numbers from matching claims
            claim_nums = [claim['claim_num'] for claim in matching_claims]
            # Process batch payment
            payment_result = self.process_batch_claim_payment(
                claim_nums,
                criteria.payment_info
            )
            if not payment_result['success']:
                # Fall back to original individual processing if batch fails
                logger.warning("[Batch Payment] Batch processing failed, falling back to individual processing")
                return self._process_eob_matching_individual(matching_claims, criteria.payment_info)
            
            # Process payment for each matching claim
            results = []
            for claim in matching_claims:
                results.append({
                    "claim_num": claim['claim_num'],
                    "success": payment_result['success'],
                    "date_of_service": claim['date_of_service'],
                    "claim_payment_num": payment_result.get('claim_payment_num') if payment_result['success'] else None,
                    "is_secondary": claim['is_secondary'],
                    "has_secondary_plan": claim['has_secondary_plan']
                })
            return {
                "success": True,
                "processed_claims": results
            }

        except Exception as e:
            logger.error(f"Error in EOB matching: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def _process_eob_matching_individual(self, matching_claims, payment_info) -> Dict[str, Any]:
        """Process EOB matching and payment using individual claim payments (fallback method)"""
        try:
            # Process payment for each matching claim
            results = []
            for claim in matching_claims:
                payment_result = self.process_batch_claim_payment(
                    claim['claim_num'],
                    payment_info
                )
                results.append({
                    "claim_num": claim['claim_num'],
                    "success": payment_result['success'],
                    "date_of_service": claim['date_of_service'],
                    "claim_payment_num": payment_result.get('claim_payment_num') if payment_result['success'] else None,
                    "is_secondary": claim['is_secondary'],
                    "has_secondary_plan": claim['has_secondary_plan']
                })
            return {
                "success": True,
                "processed_claims": results
            }
        except Exception as e:
            logger.error(f"Error in individual EOB matching: {str(e)}")
            return {"success": False, "message": str(e)}

    def process_batch_claim_payment(self, claim_nums: List[int], payment_info: PaymentInfo) -> Dict[str, Any]:
        """Process batch claim payment workflow.
        Simplified version: Directly calls the Batch endpoint without re-updating ClaimProcs/Claims.
        Assumes ClaimProcs and Claim statuses were already updated in a prior step.
        """
        try:
            logger.warning(f"=== Start Simplified Batch Claims Payment Process ===")
            logger.warning(f"[Batch Claims Payment] Processing {len(claim_nums)} claims: {claim_nums}")

            # Ensure we have claims to process
            if not claim_nums:
                return {"success": False, "message": "No claims provided for batch payment"}

            # Log payment details received
            logger.warning(f"[Batch Claims Payment] Check amount from payment info: {payment_info.check_amount}")
            logger.warning(f"[Batch Claims Payment] Check number from payment info: {payment_info.check_number}")
            if hasattr(payment_info, 'date_issued') and payment_info.date_issued:
                logger.warning(f"[Batch Claims Payment] Date issued from payment info: {payment_info.date_issued}")
            if hasattr(payment_info, 'bank_branch') and payment_info.bank_branch:
                logger.warning(f"[Batch Claims Payment] Bank branch from payment info: {payment_info.bank_branch}")
            if hasattr(payment_info, 'carrier_name') and payment_info.carrier_name:
                logger.warning(f"[Batch Claims Payment] Carrier name from payment info: {payment_info.carrier_name}")
            if hasattr(payment_info, 'pay_type') and payment_info.pay_type:
                logger.warning(f"[Batch Claims Payment] PayType from payment info: {payment_info.pay_type}")
            logger.warning(f"[Batch Claims Payment] Using provided claim numbers directly: {claim_nums}")

            # Create batch ClaimPayment
            office_tz = pytz.timezone('US/Mountain')
            current_date = datetime.now(office_tz).date()
            payment_data = {
                "claimNums": claim_nums, # Use the input list directly
                "CheckAmt": payment_info.check_amount,
                "CheckNum": payment_info.check_number,
                "CheckDate": current_date.strftime('%Y-%m-%d'),
                "CarrierName": payment_info.carrier_name if hasattr(payment_info, 'carrier_name') else None,
                "DateIssued": payment_info.date_issued if hasattr(payment_info, 'date_issued') else None,
                "BankBranch": payment_info.bank_branch if hasattr(payment_info, 'bank_branch') else None,
                "Note": payment_info.note if hasattr(payment_info, 'note') else None,
                "PayType": payment_info.pay_type if hasattr(payment_info, 'pay_type') else None
            }

            # Remove None values from payment_data
            payment_data = {k: v for k, v in payment_data.items() if v is not None}

            # Log the payload before sending
            logger.warning(f"[Batch Claims Payment] API Payload: {json.dumps(payment_data, indent=2)}")

            # Make the API call to create the batch payment
            payment_response = self.make_request(
                "claimpayments/Batch",
                method='POST',
                data=payment_data
            )

            # Log the response
            logger.warning(f"[Batch Claims Payment] API Response: {json.dumps(payment_response, indent=2, default=str)}")

            # Extract ClaimPaymentNum from response
            claim_payment_num = payment_response.get('ClaimPaymentNum')
            if not claim_payment_num:
                return {"success": False, "message": "Failed to get ClaimPaymentNum from response"}

            logger.warning(f"[Batch Claims Payment] Created batch payment #{claim_payment_num}")
            logger.warning(f"================================\n")

            # Return success and the payment number
            return {
                "success": True,
                "claim_payment_num": claim_payment_num
            }

        except Exception as e:
            logger.error(f"Error processing batch claim payment: {str(e)}")
            return {"success": False, "message": str(e)}

    ######################################################################################
    # Attach EOB Doc to the claim 
    ######################################################################################

    def attach_eob_document(self, claim_payment_num, filename, sftp_config=None):
        """Attach an EOB document to a claim payment via SFTP"""
        try:
            # Use the class's own method to load config directly.
            sftp_config = self._load_sftp_config()

            # Construct the full SFTP path
            # Note: The path should be relative to the SFTP user's root directory
            sftp_path = f"{sftp_config.get('incoming_dir', 'incoming')}/{filename}"
            
            logger.warning(f"Using SFTP path for OpenDental: {sftp_path}")

            # Prepare the payload for the OpenDental API
            payload = {
                "ClaimPaymentNum": claim_payment_num,
                "SftpAddress": f"{sftp_config['address']}/{sftp_path}",
                "SftpUsername": sftp_config["username"],
                "SftpPassword": sftp_config["password"],
            }
            
            logger.warning(f"=== Starting EOB Attachment ===")
            logger.warning(f"[EOB Attach] Processing for claim payment: {claim_payment_num}")
            logger.warning(f"[EOB Attach] Original filename: {filename}")
            logger.warning(f"[EOB Attach] Constructed SFTP path: {sftp_path}")
            logger.warning(f"[EOB Attach] Full SFTP URL: {sftp_config['address']}/{sftp_path}")
            logger.warning(f"[EOB Attach] SFTP Config - Server: {sftp_config['address']}, Username: {sftp_config['username']}")
            
            # Make the API request
            logger.warning(f"[EOB Attach] Making POST request to: eobattaches/UploadSftp")
            upload_response = self.make_request(
                'eobattaches/UploadSftp',
                'POST',
                payload
            )
            
            # Log the response
            logger.warning(f"[EOB Attach] API Response received: {upload_response}")
            
            if upload_response and upload_response.get('EobAttachNum'):
                logger.warning(f"[EOB Attach] ✓ UploadSftp successful! EobAttachNum: {upload_response.get('EobAttachNum')}")
                logger.warning(f"[EOB Attach] Full successful response: {upload_response}")
                
                # The file is moved to the processed directory by a separate GCS process later.
                # The SFTP move attempt here is redundant and was causing errors.

                return {
                    "success": True,
                    "claim_payment_num": claim_payment_num,
                    "filename": filename
                }
            
            # If the response is empty or doesn't have the expected key, it's a failure.
            logger.error("[EOB Attach] Error: UploadSftp API call did not return a valid EobAttachNum.")
            return {
                "success": False,
                "message": "Payment processed, but EOB attachment failed: No valid EobAttachNum returned from API",
                "claim_payment_num": claim_payment_num
            }
            
        except Exception as e:
            logger.error(f"\n=== EOB Attachment Error ===")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error message: {str(e)}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Fail the attachment process clearly
            return {
                "success": False,
                "message": f"Payment processed, but EOB attachment failed: {str(e)}",
                "claim_payment_num": claim_payment_num
            }

    def get_claim_procs_with_estimates(self, claim_num: int) -> Dict[str, Any]:
        """
        Retrieve claim procedures for a specific claim with detailed fee data.
        
        Args:
            claim_num: The claim number to retrieve procedures for
            
        Returns:
            Dictionary containing claim procedures with FeeBilled data
        """
        try:
            # Retrieve the ClaimProcs for this claim
            claim_procs = self.make_request(f"claimprocs?ClaimNum={claim_num}")
            
            if not claim_procs:
                return {
                    "success": False,
                    "message": f"No claim procedures found for claim #{claim_num}",
                    "procedures": []
                }
                
            logger.warning(f"Found {len(claim_procs)} procedures for claim #{claim_num}")
            
            # Extract the needed fields from each ClaimProc
            claimProcs = []
            for proc in claim_procs:
                claimProcs.append({
                    "CodeSent": proc.get("CodeSent", ""),
                    "FeeBilled": float(proc.get("FeeBilled", 0)),
                    "ClaimProcNum": proc.get("ClaimProcNum", 0),
                    "WriteOff": float(proc.get("WriteOff", 0)),
                    # Add new UCR fields from API calls
                    "matchesUCR": proc.get("matchesUCR", False),
                    "ucr_amount": float(proc.get("ucr_amount", 0))
                })
                
            return {
                "success": True,
                "claim_num": claim_num,
                "claim_procs": claimProcs
            }
            
        except Exception as e:
            logger.error(f"Error retrieving claim procs for claim #{claim_num}: {str(e)}")
            return {
                "success": False,
                "message": str(e),
                "procedures": []
            }
        