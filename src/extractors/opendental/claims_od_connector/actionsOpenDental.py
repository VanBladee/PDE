#actionsOpenDental.py
import requests
import json
import sys
import logging
import argparse
import time
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import os

load_dotenv()
# Default configuration - can be overridden by command line args
DEFAULT_MAX_WORKERS = 5  # Number of parallel threads
DEFAULT_DELAY = 0.1      # Delay between API calls in seconds
BASE_URL = os.getenv("BASE_URL")
API_KEY = os.getenv("API_KEY")
HEADERS = {"Authorization": f"{API_KEY}"}

def get_claim_procs(claim_num):
    """
    Get all ClaimProcs associated with a given claim number.
    """
    url = f"{BASE_URL}/claimprocs?ClaimNum={claim_num}"
    
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()  # This will raise an HTTPError for 4XX/5XX responses
        claim_procs = response.json()
        logging.info(f"Found {len(claim_procs)} ClaimProcs for Claim #{claim_num}")
        return claim_procs
    except requests.exceptions.HTTPError as e:
        logging.error(f"Error retrieving ClaimProcs for Claim #{claim_num}: {str(e)}")
        raise  # Re-raise the exception for the caller to handle
    except Exception as e:
        logging.error(f"Error retrieving ClaimProcs for Claim #{claim_num}: {str(e)}")
        return []

def detach_from_payment(claim_proc_id, payment_num, delay=DEFAULT_DELAY):
    """Detach a claim procedure from its payment."""
    if payment_num == 0:
        return True  # Nothing to detach
        
    url = f"{BASE_URL}/claimprocs/{claim_proc_id}"
    detach_data = {"ClaimPaymentNum": 0}
    logging.info(f"Detaching ClaimProc #{claim_proc_id} from payment #{payment_num}")
    
    try:
        detach_response = requests.put(url, headers=HEADERS, json=detach_data)
        if detach_response.status_code != 200:
            logging.error(f"Failed to detach ClaimProc #{claim_proc_id} from payment: {detach_response.text}")
            return False
        logging.info(f"Successfully detached ClaimProc #{claim_proc_id} from payment #{payment_num}")
        
        # Add configurable delay to avoid overloading the API
        if delay > 0:
            time.sleep(delay)
        return True
    except Exception as e:
        logging.error(f"Error detaching ClaimProc #{claim_proc_id}: {str(e)}")
        return False

def reset_proc_status(claim_proc_id, delay=DEFAULT_DELAY):
    """Reset procedure status to NotReceived and zero out payment amounts."""
    url = f"{BASE_URL}/claimprocs/{claim_proc_id}"
    data = {
        "Status": "NotReceived",
        "InsPayAmt": "0.00",
        "WriteOff": "0.00",
        "Remarks": ""
    }
    
    try:
        response = requests.put(url, headers=HEADERS, json=data)
        if response.status_code != 200:
            logging.error(f"Failed to update ClaimProc #{claim_proc_id}: {response.text}")
            return False
        logging.info(f"Reset ClaimProc #{claim_proc_id}")
        return True
    except Exception as e:
        logging.error(f"Error resetting status for ClaimProc #{claim_proc_id}: {str(e)}")
        return False

def reset_claim_proc(claim_proc_id, delay=DEFAULT_DELAY):
    """Reset a claim procedure to NotReceived status and zero payment amounts."""
    # First, get the current ClaimProc to check its status
    get_url = f"{BASE_URL}/claimprocs/{claim_proc_id}"
    
    try:
        get_response = requests.get(get_url, headers=HEADERS)
        get_response.raise_for_status()
        claim_proc = get_response.json()
        
        # Check if the response is a list (API inconsistency)
        if isinstance(claim_proc, list):
            if not claim_proc:  # Empty list
                logging.error(f"ClaimProc #{claim_proc_id} not found")
                return False
            claim_proc = claim_proc[0]  # Take the first item if it's a list
        
        # Extract important details for logging
        proc_code = claim_proc.get("CodeSent", "Unknown")
        ins_pay_amt = claim_proc.get("InsPayAmt", "0.00")
        status = claim_proc.get("Status", "Unknown")
        claim_payment_num = claim_proc.get("ClaimPaymentNum", 0)
        
        logging.info(f"Processing ClaimProc #{claim_proc_id} (Code: {proc_code}, Status: {status}, Payment: ${ins_pay_amt}, ClaimPaymentNum: {claim_payment_num})")
        
        # Check if this is a special type that can't be updated directly
        if claim_proc.get("IsTransfer") == "true" or claim_proc.get("Status") in ["Adjustment", "InsHist", "CapClaim", "CapComplete", "CapEstimate"]:
            logging.warning(f"ClaimProc #{claim_proc_id} (Code: {proc_code}) has status '{status}' or IsTransfer=true and cannot be updated directly")
            return False
        
        # STEP 1: First detach from claim payment if needed
        if claim_payment_num != 0:
            if not detach_from_payment(claim_proc_id, claim_payment_num, delay):
                return False
        
        # STEP 2: Now update the status and payment fields
        return reset_proc_status(claim_proc_id, delay)
    except Exception as e:
        logging.error(f"Error resetting ClaimProc #{claim_proc_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def reset_claim_status(claim_id):
    """Reset a claim to Sent status."""
    url = f"{BASE_URL}/claims/{claim_id}"
    data = {"ClaimStatus": "S"}  # Sent
    
    try:
        response = requests.put(url, headers=HEADERS, json=data)
        response.raise_for_status()
        logging.info(f"Reset claim #{claim_id} status to Sent")
        return True
    except Exception as e:
        logging.error(f"Error resetting claim #{claim_id}: {str(e)}")
        return False

def delete_payment(payment_num):
    """Delete a claim payment (If no EOB is attached)"""
    try:
        delete_url = f"{BASE_URL}/claimpayments/{payment_num}"
        delete_response = requests.delete(delete_url, headers=HEADERS)
        
        if delete_response.status_code == 200:
            logging.info(f"Successfully deleted ClaimPayment #{payment_num}")
            return True
        else:
            logging.error(f"Failed to delete ClaimPayment #{payment_num}: {delete_response.text}")
            return False
    except Exception as e:
        logging.error(f"Error deleting ClaimPayment #{payment_num}: {str(e)}")
        return False

def process_claim_procs_parallel(claim_procs, max_workers=DEFAULT_MAX_WORKERS, delay=DEFAULT_DELAY):
    """Process a list of claim procedures in parallel, returning results statistics."""
    results = {'successful_procs': 0, 'failed_procs': 0, 'total_procs': len(claim_procs)}
    proc_ids = [proc.get("ClaimProcNum") for proc in claim_procs]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(reset_claim_proc, proc_id, delay): proc_id for proc_id in proc_ids}
        
        for future in concurrent.futures.as_completed(futures):
            proc_id = futures[future]
            try:
                if future.result():
                    results['successful_procs'] += 1
                else:
                    results['failed_procs'] += 1
            except Exception as e:
                logging.error(f"Exception processing ClaimProc #{proc_id}: {str(e)}")
                results['failed_procs'] += 1
    
    return results

def test_getProcs(claim_num, max_workers=DEFAULT_MAX_WORKERS, delay=DEFAULT_DELAY):
    """
    Main function to test getting and resetting ClaimProcs for a specific claim number.
    Uses parallel processing for faster execution.
    """
    logging.info(f"Starting test for Claim #{claim_num} with {max_workers} parallel workers")
    
    # 1. Get all ClaimProcs for the specified claim
    claim_procs = get_claim_procs(claim_num)
    
    if not claim_procs:
        logging.warning(f"No ClaimProcs found for Claim #{claim_num}")
        return False
    
    # 2. Display the ClaimProcs (for informational purposes)
    logging.info("ClaimProcs found:")
    total_payment = 0.0
    for idx, proc in enumerate(claim_procs):
        proc_code = proc.get("CodeSent", "Unknown")
        fee_billed = proc.get("FeeBilled", "0.00")
        ins_pay_amt = proc.get("InsPayAmt", "0.00")
        try:
            total_payment += float(ins_pay_amt)
        except ValueError:
            pass
        logging.info(f"  {idx+1}. ClaimProc #{proc.get('ClaimProcNum')} - Code: {proc_code}, Billed: ${fee_billed}, Payment: ${ins_pay_amt}")
    
    logging.info(f"Total payment amount for this claim: ${total_payment:.2f}")
    
    # 3. Reset each ClaimProc in parallel
    results = process_claim_procs_parallel(claim_procs, max_workers, delay)
    
    logging.info(f"Successfully reset {results['successful_procs']} out of {results['total_procs']} ClaimProcs")
    
    # 4. Reset the claim status
    reset_claim_status(claim_num)
    
    logging.info(f"Test completed for Claim #{claim_num}")
    return True

def process_revert_file(json_file_path, max_workers=DEFAULT_MAX_WORKERS, delay=DEFAULT_DELAY):
    """
    Process a JSON file containing batch claims and procedures to revert.
    Uses parallel processing for faster execution.
    """
    try:
        with open(json_file_path, 'r') as f:
            revert_data = json.load(f)
        
        batch_info = revert_data.get('batchPayment', {})
        logging.info(f"Starting batch reversion for batch #{batch_info.get('id')} with {max_workers} parallel workers")
        logging.info(f"Batch details: Check #{batch_info.get('checkNumber')} from {batch_info.get('carrierName')}")
        
        results = {'successful_procs': 0, 'failed_procs': 0, 'total_procs': 0, 'deleted_payments': 0}
        claim_payment_nums = set()  # Track unique ClaimPaymentNums to delete later
        all_claim_procs_data = []  # Store ClaimProc data for parallel processing
        
        # First, collect all claim and proc data
        for patient in revert_data.get('patients', []):
            patient_name = f"{patient.get('firstName', '')} {patient.get('lastName', '')}"
            logging.info(f"Processing patient: {patient_name}")
            
            for claim in patient.get('claims', []):
                claim_num = claim.get('internalClaimNum')
                logging.info(f"Collecting ClaimProcs for claim #{claim_num}")
                
                # Get all ClaimProcs for this claim
                claim_procs = get_claim_procs(claim_num)
                
                # Collect ClaimPaymentNums
                for proc in claim_procs:
                    payment_num = proc.get("ClaimPaymentNum", 0)
                    if payment_num != 0:
                        claim_payment_nums.add(payment_num)
                
                # Store ClaimProcs data along with claim number
                for proc in claim_procs:
                    all_claim_procs_data.append({
                        'proc': proc,
                        'claim_num': claim_num
                    })
        
        # Step 1: Update claim statuses in parallel FIRST
        claims_to_update = set(item['claim_num'] for item in all_claim_procs_data)
        logging.info(f"Updating status for {len(claims_to_update)} claims")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(reset_claim_status, claim_num): claim_num for claim_num in claims_to_update}
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    claim_num = futures[future]
                    logging.error(f"Exception updating claim #{claim_num}: {str(e)}")
        
        # Add a small delay after claim status updates
        time.sleep(delay)
        
        # Step 2: Process all procs by detaching and resetting them
        procs_to_process = [data['proc'].get('ClaimProcNum') for data in all_claim_procs_data]
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results['total_procs'] = len(procs_to_process)
            futures = {executor.submit(reset_claim_proc, proc_id, delay): proc_id for proc_id in procs_to_process}
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    if future.result():
                        results['successful_procs'] += 1
                    else:
                        results['failed_procs'] += 1
                except Exception as e:
                    proc_id = futures[future]
                    logging.error(f"Exception resetting ClaimProc #{proc_id}: {str(e)}")
                    results['failed_procs'] += 1
        
        # Step 3: Delete the ClaimPayments in parallel
        logging.info(f"Deleting {len(claim_payment_nums)} ClaimPayments")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            payment_futures = {executor.submit(delete_payment, payment_num): payment_num for payment_num in claim_payment_nums}
            
            for future in concurrent.futures.as_completed(payment_futures):
                payment_num = payment_futures[future]
                try:
                    if future.result():
                        results['deleted_payments'] += 1
                except Exception as e:
                    logging.error(f"Exception deleting payment #{payment_num}: {str(e)}")
        
        logging.info(f"Batch reversion complete. Successful procs: {results['successful_procs']}, Failed: {results['failed_procs']}, Total: {results['total_procs']}, Deleted payments: {results['deleted_payments']}")
        return results
        
    except Exception as e:
        logging.error(f"Error processing revert file: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}

def revert_claim_payment(payment_num, max_workers=DEFAULT_MAX_WORKERS, delay=DEFAULT_DELAY):
    """
    Process all ClaimProcs associated with a specific ClaimPayment number.
    Detaches the procs, resets them, and then deletes the payment.
    """
    logging.info(f"Processing ClaimPayment #{payment_num} with {max_workers} parallel workers")
    results = {'successful_procs': 0, 'failed_procs': 0, 'total_procs': 0, 'deleted_payments': 0}
    
    # Step 1: Get all ClaimProcs associated with this payment
    url = f"{BASE_URL}/claimprocs?ClaimPaymentNum={payment_num}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        claim_procs = response.json()
        
        if not claim_procs:
            logging.warning(f"No ClaimProcs found for ClaimPayment #{payment_num}")
            return results
        
        results['total_procs'] = len(claim_procs)
        logging.info(f"Found {len(claim_procs)} ClaimProcs associated with ClaimPayment #{payment_num}")
        
        # Collect claim numbers for later status update
        claim_nums = set(proc.get("ClaimNum", 0) for proc in claim_procs if proc.get("ClaimNum", 0) != 0)
        
        # IMPORTANT: Step 2 - Update claim statuses FIRST
        logging.info(f"Updating status for {len(claim_nums)} claims")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            claim_futures = {executor.submit(reset_claim_status, claim_num): claim_num for claim_num in claim_nums}
            for future in concurrent.futures.as_completed(claim_futures):
                try:
                    future.result()  # Just ensure completion
                except Exception as e:
                    claim_num = claim_futures[future]
                    logging.error(f"Exception updating claim #{claim_num}: {str(e)}")
                    
        # Add a small delay after claim status updates
        time.sleep(delay)
        
        # Step 3: Process all ClaimProcs
        proc_results = process_claim_procs_parallel(claim_procs, max_workers, delay)
        results.update(proc_results)
        
        # Step 4: Delete the ClaimPayment
        if delete_payment(payment_num):
            results['deleted_payments'] = 1
        
        logging.info(f"ClaimPayment #{payment_num} processing complete. Successful procs: {results['successful_procs']}, Failed: {results['failed_procs']}, Total: {results['total_procs']}")
        return results
        
    except Exception as e:
        logging.error(f"Error processing ClaimPayment #{payment_num}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}

def process_claim(claim_num, max_workers=DEFAULT_MAX_WORKERS, delay=DEFAULT_DELAY):
    """
    Process a specific claim by claim number.
    Gets all procedures on the claim, detaches them from payments, resets them,
    and updates the claim status.
    """
    logging.info(f"Processing Claim #{claim_num} with {max_workers} parallel workers")
    results = {'successful_procs': 0, 'failed_procs': 0, 'total_procs': 0, 'affected_payments': set()}
    
    # Step 1: Get all ClaimProcs for this claim
    try:
        claim_procs = get_claim_procs(claim_num)
    except requests.exceptions.HTTPError as e:
        logging.error(f"Error retrieving ClaimProcs for Claim #{claim_num}: {str(e)}")
        # Add error code to results
        results['error'] = str(e)
        results['error_code'] = e.response.status_code if hasattr(e, 'response') and hasattr(e.response, 'status_code') else None
        return results
    except Exception as e:
        logging.error(f"Error retrieving ClaimProcs for Claim #{claim_num}: {str(e)}")
        results['error'] = str(e)
        return results
    
    if not claim_procs:
        logging.warning(f"No ClaimProcs found for Claim #{claim_num}")
        return results
    
    results['total_procs'] = len(claim_procs)
    
    # Display summary of found procs
    total_payment = 0.0
    logging.info("ClaimProcs found:")
    for idx, proc in enumerate(claim_procs):
        proc_code = proc.get("CodeSent", "Unknown")
        fee_billed = proc.get("FeeBilled", "0.00")
        ins_pay_amt = proc.get("InsPayAmt", "0.00")
        payment_num = proc.get("ClaimPaymentNum", 0)
        if payment_num != 0:
            results['affected_payments'].add(payment_num)
        
        try:
            total_payment += float(ins_pay_amt)
        except ValueError:
            pass
        logging.info(f"  {idx+1}. ClaimProc #{proc.get('ClaimProcNum')} - Code: {proc_code}, Billed: ${fee_billed}, Payment: ${ins_pay_amt}, PaymentNum: {payment_num}")
    
    logging.info(f"Total payment amount for this claim: ${total_payment:.2f}")
    logging.info(f"This claim has procedures attached to {len(results['affected_payments'])} payments")
    
    # IMPORTANT: Step 2 - Reset the claim status FIRST to avoid API error
    logging.info(f"Resetting claim #{claim_num} status to Sent first")
    reset_claim_status(claim_num)
    
    # Add a small delay after claim status update
    time.sleep(delay)
    
    # Step 3: Process all ClaimProcs
    proc_results = process_claim_procs_parallel(claim_procs, max_workers, delay)
    results.update(proc_results)
    
    logging.info(f"Claim #{claim_num} processing complete. Successfully reset {results['successful_procs']} out of {results['total_procs']} ClaimProcs")
    
    # Step 4: List the payment numbers that might need to be reviewed
    if results['affected_payments']:
        logging.info(f"The following payment numbers were affected and might need separate processing: {', '.join(map(str, results['affected_payments']))}")
        logging.info("You can process these payments individually using the --payment-num option if needed")
    
    return results

if __name__ == "__main__":
    # Check if any command line arguments were provided
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        # Simple usage: python test_clearProcsFromClaim.py 120
        claim_num = int(sys.argv[1])
        max_workers = DEFAULT_MAX_WORKERS
        delay = DEFAULT_DELAY
        
        # If additional parameters are provided
        if len(sys.argv) > 2 and sys.argv[2].isdigit():
            max_workers = int(sys.argv[2])
        if len(sys.argv) > 3:
            try:
                delay = float(sys.argv[3])
            except ValueError:
                pass
                
                #INSERT CLAIM NUM TO RESET CLAIM AND IT'S PROCS
        process_claim(claim_num, max_workers, delay)
        
        
    else:
        # Original argument parser for more complex usage
        parser = argparse.ArgumentParser(description="Reset claim procedures and payments in Open Dental.")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--claim-num", type=int, help="The claim number to process")
        group.add_argument("--revert-file", type=str, help="Path to a JSON file containing batch claims to revert")
        group.add_argument("--payment-num", type=int, help="The ClaimPayment number to process")
        
        # Add performance tuning parameters
        parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS, 
                          help=f"Maximum number of parallel workers (default: {DEFAULT_MAX_WORKERS})")
        parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, 
                          help=f"Delay between API calls in seconds (default: {DEFAULT_DELAY})")
        
        args = parser.parse_args()
        
        try:
            if args.claim_num:
                process_claim(args.claim_num, args.max_workers, args.delay)
            elif args.revert_file:
                process_revert_file(args.revert_file, args.max_workers, args.delay)
            elif args.payment_num:
                revert_claim_payment(args.payment_num, args.max_workers, args.delay)
        except Exception as e:
            logging.error(f"Unhandled exception: {str(e)}")
            sys.exit(1)
