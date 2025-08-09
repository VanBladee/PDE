from typing import TypedDict, Any, Dict, Optional, List, Union, Set # Added Set
from dataclasses import dataclass
from datetime import datetime, date # Added for SearchCriteria and potential use in methods
import re # Added import for regular expressions
import collections # Added import for collections module

# Import logging configuration to match celery task logging
from backend.logging_config import get_logger, LOG_INFO, LOG_ERROR, LOG_SUCCESS, LOG_WARNING, LOG_SECTION_START, LOG_SECTION_END, LOG_SUBSECTION

# Configure a logger for this module
logger = get_logger(__name__, worker_type="CLAIMS-WORKER")

# NicknameMapper Class Definition (as provided by user)
class NicknameMapper:
    # Bidirectional nickname mappings
    NICKNAME_GROUPS = [
        # Common English nicknames
        {'william', 'will', 'bill', 'billy', 'willy', 'liam'},
        {'robert', 'rob', 'bob', 'bobby', 'robbie', 'bert'},
        {'richard', 'rich', 'rick', 'ricky', 'dick', 'richie'},
        {'michael', 'mike', 'mikey', 'mick', 'mickey', 'miguel'},
        {'james', 'jim', 'jimmy', 'jamie', 'jimbo'},
        {'john', 'johnny', 'jack', 'jackie', 'jon'},
        {'joseph', 'joe', 'joey', 'jose'},
        {'thomas', 'tom', 'tommy', 'thom'},
        {'charles', 'charlie', 'chuck', 'chas', 'chaz'},
        {'christopher', 'chris', 'kit', 'topher'},
        {'matthew', 'matt', 'matty'},
        {'anthony', 'tony', 'ant'},
        {'daniel', 'dan', 'danny'},
        {'david', 'dave', 'davey'},
        {'kenneth', 'ken', 'kenny'},
        {'stephen', 'steve', 'steven', 'stevie'},
        {'andrew', 'andy', 'drew'},
        {'edward', 'ed', 'eddie', 'ted', 'teddy', 'ned'},
        {'lawrence', 'larry', 'lars'},
        {'samuel', 'sam', 'sammy'},
        {'benjamin', 'ben', 'benny', 'benji'},
        {'alexander', 'alex', 'al', 'xander', 'lex'},
        {'nicholas', 'nick', 'nicky', 'nico'},
        
        # Female names
        {'elizabeth', 'liz', 'lizzie', 'beth', 'betty', 'betsy', 'eliza', 'lisa'},
        {'margaret', 'maggie', 'meg', 'peggy', 'marge', 'margie', 'greta'},
        {'katherine', 'kate', 'katie', 'kathy', 'kat', 'kitty', 'catherine', 'cathy'},
        {'patricia', 'pat', 'patty', 'patsy', 'trish', 'tricia'},
        {'jennifer', 'jen', 'jenny'},
        {'jessica', 'jess', 'jessie'},
        {'deborah', 'deb', 'debbie', 'debby'},
        {'susan', 'sue', 'susie', 'suzy'},
        {'dorothy', 'dot', 'dottie', 'dolly'},
        {'barbara', 'barb', 'barbie', 'babs'},
        {'rebecca', 'becca', 'becky'},
        {'christine', 'chris', 'chrissy', 'tina'},
        {'victoria', 'vicky', 'vic', 'tori'},
        {'alexandra', 'alex', 'lexi', 'lexie', 'sandra', 'sandy'},
        {'stephanie', 'steph', 'stephie'},
        {'michelle', 'shelly', 'michi'},
        {'kimberly', 'kim', 'kimmy'},
        {'abigail', 'abby', 'gail'},
        {'amanda', 'mandy', 'manda'},
        {'angela', 'angie', 'angel'},
        
        # Spanish/Hispanic variations
        {'francisco', 'frank', 'pancho', 'paco', 'cisco'},
        {'guadalupe', 'lupe', 'lupita'},
        {'jose', 'pepe', 'joe'},
        {'ignacio', 'nacho'},
        {'rafael', 'rafa'},
        {'enrique', 'henry', 'quique'},
        {'guillermo', 'william', 'memo'},
        {'alejandro', 'alex', 'alejo'},
        {'roberto', 'robert', 'beto'},
        
        # Additional variations
        {'gerald', 'gerry', 'jerry'},
        {'raymond', 'ray'},
        {'ronald', 'ron', 'ronnie'},
        {'donald', 'don', 'donnie'},
        {'harold', 'harry', 'hal'},
        {'francis', 'frank', 'fran'},
        {'eugene', 'gene'},
        {'phillip', 'phil', 'philip'},
        {'timothy', 'tim', 'timmy'},
        {'gregory', 'greg', 'gregg'},
    ]
    
    def __init__(self):
        # Build lookup dictionaries for O(1) access
        self._nickname_to_group = {}
        self._build_lookup_tables()
    
    def _build_lookup_tables(self):
        """Build reverse lookup tables for efficient nickname resolution"""
        for idx, name_group in enumerate(self.NICKNAME_GROUPS):
            for name in name_group:
                self._nickname_to_group[name.lower()] = idx
    
    def get_name_variations(self, name: str) -> Set[str]:
        """Get all possible variations of a name including nicknames"""
        name_lower = name.lower().strip()
        
        # Always include the original name
        variations = {name_lower}
        
        # Find the nickname group this name belongs to
        if name_lower in self._nickname_to_group:
            group_idx = self._nickname_to_group[name_lower]
            variations.update(self.NICKNAME_GROUPS[group_idx])
        
        return variations
    
    def are_names_related(self, name1: str, name2: str) -> bool:
        """Check if two names are related (same person, different variations)"""
        # Ensure inputs are stripped and lowercased for consistent lookup
        name1_lower = name1.lower().strip()
        name2_lower = name2.lower().strip()
        if not name1_lower or not name2_lower:
            return False # Cannot be related if one is empty
        return bool(self.get_name_variations(name1_lower) & self.get_name_variations(name2_lower))

@dataclass
class ProcedurePayment: # Copied from claimsOpenDental.py as it's used by PaymentInfo
    proc_code: str
    submitted_amt: float
    amount_paid: float
    remarks: str
    deductible: float = 0.0
    writeoff: float = 0.0
    markAsNotReceived: bool = False

@dataclass
class PaymentInfo: # Copied from claimsOpenDental.py as it's used by SearchCriteria
    procedures: List[ProcedurePayment]
    check_number: str | None = None
    check_amount: float | None = None
    date_issued: str | None = None
    bank_branch: str | None = None
    carrier_name: str | None = None
    pay_type: int | None = None
    note: str | None = None

@dataclass
class SearchCriteria:
    date_of_service: str
    patient_first_name: str
    patient_last_name: str
    subscriber_first_name: str
    subscriber_last_name: str
    payment_info: PaymentInfo

class ClaimMatch(TypedDict):
    claim_num: int
    pat_num: int
    claim_fee: float
    date_of_service: str
    date_sent: Optional[str] = None  # Added DateSent field
    date_received: Optional[str] = None  # Added DateReceived field
    claim_note: str
    is_secondary: bool
    has_secondary_plan: bool
    has_pending_secondary: bool
    match_score: Optional[int] = None
    match_source: Optional[str] = None
    claim_procs: Optional[List[Dict]] = None
    isOrtho: Optional[bool] = None # Added for ortho claims
    ortho_details: Optional[Dict[str, Any]] = None # Added for ortho claims
    is_supplemental: Optional[bool] = False # Added for supplemental claims
    carrier_name: Optional[str] = None # Added to pass carrier name from matched claims
    claim_status: Optional[str] = None # Added to track claim status ('S', 'H', 'R', etc.)

class ClaimMatcher:
    def __init__(self, make_request_callable, pms_data=None):
        self.make_request = make_request_callable
        self.pms_data = pms_data # Will be used by methods needing it
        self.nickname_mapper = NicknameMapper()  # Add nickname support
        self._compiled_regex_cache = {} # Cache compiled regexes
        self._nickname_cache = {}  # Cache nickname lookups (currently unused based on provided NicknameMapper)

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
            
            # Handle different patterns based on token length
            if len(token) == 1:  # Initial
                # Match as initial (possibly followed by dot or longer name)
                regex_parts.append(fr'(?:\b{escaped_token}(?:\.|[a-z]*)\b)')
            elif len(token) == 2:  # Very short name or partial
                # For very short names, be more restrictive but still allow flexibility
                patterns = [
                    fr'\b{escaped_token}[a-z]{{0,3}}\b',  # Original pattern
                    fr'[a-z]*{escaped_token}\b',          # ENHANCED: Match as suffix
                    fr'\b[a-z]*{escaped_token}[a-z]*\b'   # ENHANCED: Match as contained substring
                ]
                regex_parts.append(f'(?:{"|".join(patterns)})')
            else:  # Longer name part
                # Dynamic minimum prefix length based on name length
                min_prefix_len = min(2, len(token) - 1)  # Smaller threshold for shorter names
                
                patterns = []
                
                # Full match (possibly with additional characters)
                patterns.append(fr'\b{escaped_token}[a-z]*\b')
                
                # ENHANCED: Add suffix matching for truncated names
                if len(token) >= 2:
                    patterns.append(fr'[a-z]*{escaped_token}\b')  # Match as suffix
                
                # ENHANCED: Add substring matching for partial names
                if len(token) >= 3:
                    patterns.append(fr'\b[a-z]*{escaped_token}[a-z]*\b')  # Match as substring
                
                # NEW: Try matching without the first letter (for typos like Dthunell -> Thunell)
                if len(token) >= 5:  # Only for reasonably long names
                    without_first = token[1:]
                    escaped_without_first = re.escape(without_first)
                    patterns.append(fr'\b{escaped_without_first}[a-z]*\b')
                
                # First letter + fuzzy middle + last letter(s) for longer names
                # This helps catch spelling variations like "catherine" vs "katherine"
                if len(token) >= 4:
                    first_letter = escaped_token[0]
                    last_part = escaped_token[-2:] if len(token) > 4 else escaped_token[-1]
                    middle_len = len(token) - len(last_part) - 1
                    # Allow flexible middle with some length constraints
                    patterns.append(fr'\b{first_letter}[a-z]{{{max(1, middle_len-1)},{middle_len+1}}}' + 
                                re.escape(last_part) + r'[a-z]*\b')
                
                # Prefix matching with adaptive length
                for prefix_len in range(len(token)-1, min_prefix_len-1, -1):
                    prefix = token[:prefix_len]
                    escaped_prefix = re.escape(prefix)
                    # More permissive pattern for longer prefixes
                    patterns.append(fr'\b{escaped_prefix}[a-z]*\b')
                
                # Combine all patterns for this token
                regex_parts.append(f'(?:{"|".join(patterns)})')
        
        # Join with flexible pattern between tokens
        # The (?:.*?| ) means either some characters or just a space between tokens
        final_regex = r'(?:.*?| )'.join(regex_parts)
        return final_regex

    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        if len(s1) < len(s2):
            return ClaimMatcher.levenshtein_distance(s2, s1)
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
    def normalize_procedure_code(code: str) -> str:
        if not code:
            return code
        if code.startswith('D') and len(code) > 5 and code[1:].isdigit():
            digits = code[1:]
            if len(digits) > 4:
                while len(digits) > 4 and digits[0] == '0':
                    digits = digits[1:]
            code = 'D' + digits
        elif not code.startswith('D') and code.isdigit():
            code = 'D' + code
        return code

    def _match_procedure_codes(self, payment_codes: List[str], db_codes: List[str]) -> Dict[str, Union[float, int, List[str]]]:
        """
        Compare procedure codes from the payment and database to calculate match percentage.
        Enhanced to handle ortho claims with multiple identical codes.
        """
        if not payment_codes or not db_codes:
            return {'match_percentage': 0.0, 'matched_codes': []}
        
        # Special case for ortho claims (multiple identical codes)
        if len(set(payment_codes)) == 1 and len(set(db_codes)) == 1:
            # If both lists contain exclusively one unique code (repeated multiple times)
            payment_unique_code = payment_codes[0]
            db_unique_code = db_codes[0]
            
            # If the unique codes match (after normalization)
            if self.normalize_procedure_code(payment_unique_code) == self.normalize_procedure_code(db_unique_code):
                return {
                    'match_percentage': 1.0,
                    'matched_codes': [payment_unique_code]
                }
        
        # Regular matching for non-ortho or mixed code scenarios
        matched_codes = []
        payment_code_set = set(payment_codes)
        db_code_set = set(db_codes)
        
        # First, normalize all codes for comparison
        normalized_payment_codes = {self.normalize_procedure_code(code) for code in payment_code_set}
        normalized_db_codes = {self.normalize_procedure_code(code) for code in db_code_set}
        
        # Find intersection of normalized codes
        matching_normalized_codes = normalized_payment_codes.intersection(normalized_db_codes)
        
        # Count matches using original payment codes to preserve them for the result
        for pcode in payment_code_set:
            if self.normalize_procedure_code(pcode) in matching_normalized_codes:
                matched_codes.append(pcode)
        
        # Calculate match percentage based on unique codes
        total_unique_codes = len(normalized_payment_codes.union(normalized_db_codes))
        match_count = len(matching_normalized_codes)
        
        match_percentage = match_count / len(normalized_payment_codes) if normalized_payment_codes else 0.0
        
        return {
            'match_percentage': match_percentage,
            'matched_codes': matched_codes
        }

    def _get_compiled_regex(self, pattern: str) -> re.Pattern:
        """Cache compiled regex patterns"""
        if pattern not in self._compiled_regex_cache:
            self._compiled_regex_cache[pattern] = re.compile(pattern, re.IGNORECASE)
        return self._compiled_regex_cache[pattern]

    def _build_regex_for_name_with_nicknames(self, query_name: str) -> str:
        """Build regex that includes nickname variations and handles multi-part names"""
        if not query_name or not query_name.strip():
            return r".*"
        
        query_name_clean = query_name.strip().lower()
        
        # Split the query name into parts (handle spaces, hyphens, apostrophes)
        name_parts = re.split(r'[-\s\']+', query_name_clean)
        name_parts = [part for part in name_parts if part]  # Remove empty strings
        
        if not name_parts:
            return r".*"
        
        # Handle single part names (most common case)
        if len(name_parts) == 1:
            name_variations = self.nickname_mapper.get_name_variations(name_parts[0])
            regex_patterns = []
            for variation in name_variations:
                pattern = ClaimMatcher._build_regex_for_name_part(variation)
                regex_patterns.append(pattern)
            
            if not regex_patterns:
                return r".*"
            combined_pattern = f"(?:{'|'.join(regex_patterns)})" if len(regex_patterns) > 1 else regex_patterns[0]
            logger.info(LOG_INFO.format(f"Built nickname-aware regex for '{query_name}': Found {len(name_variations)} variations, pattern: {combined_pattern}"))
            return combined_pattern
        
        # Handle multi-part names (e.g., "Emma Michelle")
        all_part_patterns = []
        total_variations = 0
        
        for part in name_parts:
            part_variations = self.nickname_mapper.get_name_variations(part)
            total_variations += len(part_variations)
            part_patterns = []
            for variation in part_variations:
                pattern = ClaimMatcher._build_regex_for_name_part(variation)
                part_patterns.append(pattern)
            
            if part_patterns:
                # Each part can match any of its variations
                part_combined = f"(?:{'|'.join(part_patterns)})" if len(part_patterns) > 1 else part_patterns[0]
                all_part_patterns.append(part_combined)
        
        if not all_part_patterns:
            return r".*"
        
        # Create flexible matching patterns:
        # 1. Match all parts in order (with flexible separator)
        # 2. Match just the first part (for cases where DB only has first name)
        # 3. Match any combination of parts
        
        flexible_patterns = []
        
        # Pattern 1: Match just the first part (most important for cases like "Emma" matching "Emma Michelle")
        flexible_patterns.append(all_part_patterns[0])
        
        # Pattern 2: Match all parts in sequence (traditional full match)
        if len(all_part_patterns) > 1:
            full_match_pattern = r'(?:.*?|\s+)'.join(all_part_patterns)
            flexible_patterns.append(full_match_pattern)
        
        # Combine all flexible patterns
        final_pattern = f"(?:{'|'.join(flexible_patterns)})"
        
        logger.info(LOG_INFO.format(f"Built nickname-aware regex for multi-part name '{query_name}': Found {total_variations} total variations across {len(name_parts)} parts, pattern: {final_pattern}"))
        return final_pattern

    def _calculate_name_match_score_with_nicknames(
        self, 
        claim_patient_fn: Optional[str], 
        claim_patient_ln: Optional[str],
        criteria_patient_fn_query: str, 
        criteria_patient_ln_query: str,
        log_prefix: str = ""
    ) -> int:
        """Enhanced name matching with nickname support"""
        
        if not criteria_patient_fn_query:
            logger.warning(LOG_WARNING.format(f"{log_prefix} Name score: 0 (criteria_patient_fn_query missing or empty)"))
            return 0

        crit_fn_q = criteria_patient_fn_query.strip().lower()
        crit_ln_q = criteria_patient_ln_query.strip().lower() if criteria_patient_ln_query else ""

        if not crit_fn_q:
            logger.warning(LOG_WARNING.format(f"{log_prefix} Name score: 0 (crit_fn_q empty post-strip)"))
            return 0

        claim_fn_clean = claim_patient_fn.strip().lower() if claim_patient_fn else ""
        claim_ln_clean = claim_patient_ln.strip().lower() if claim_patient_ln else ""

        if not claim_fn_clean:
            logger.info(LOG_INFO.format(f"{log_prefix} Name score: 0 (Claim has no first name ('{claim_fn_clean}') to match criteria '{crit_fn_q}')"))
            return 0

        # First name matching with nickname support
        fn_score_component = 0
        
        # Try direct nickname relationship first (faster)
        if self.nickname_mapper.are_names_related(crit_fn_q, claim_fn_clean):
            fn_score_component = 15
            logger.info(LOG_INFO.format(
                f"{log_prefix}   FN match: YES via nickname relationship ('{claim_fn_clean}' ~ '{crit_fn_q}'). FN Score: 15"
            ))
        else:
            # Fall back to regex matching with nickname variations
            try:
                fn_regex_pattern = self._build_regex_for_name_with_nicknames(crit_fn_q)
                if self._get_compiled_regex(fn_regex_pattern).search(claim_fn_clean):
                    fn_score_component = 15
                    logger.info(LOG_INFO.format(
                        f"{log_prefix}   FN match: YES ('{claim_fn_clean}' vs nickname-aware regex for '{crit_fn_q}'). FN Score: 15"
                    ))
                else:
                    logger.info(LOG_INFO.format(
                        f"{log_prefix}   FN match: NO ('{claim_fn_clean}' vs nickname-aware regex for '{crit_fn_q}'). FN Score: 0. Total Name Score: 0"
                    ))
                    return 0 # First name must match
            except re.error as e:
                logger.error(LOG_ERROR.format(f"{log_prefix} Regex error during FN scoring: {e}. Query FN: '{crit_fn_q}'. Pattern: '{fn_regex_pattern if 'fn_regex_pattern' in locals() else 'N/A'}'. Returning 0."))
                return 0

        # Last name matching (keeping existing logic, adapted for compiled regex)
        ln_score_component = 0
        if crit_ln_q:
            if not claim_ln_clean:
                logger.info(LOG_INFO.format(f"{log_prefix}   LN match: Claim has no LN to match criteria LN '{crit_ln_q}'. LN Score: 0"))
            else:
                try:
                    # Attempt 1: Match full criteria LN against claim LN
                    full_ln_regex_pattern = ClaimMatcher._build_regex_for_name_part(crit_ln_q)
                    if self._get_compiled_regex(full_ln_regex_pattern).search(claim_ln_clean):
                        ln_score_component = 15
                        logger.info(LOG_INFO.format(f"{log_prefix}   LN full match: YES ('{claim_ln_clean}' vs regex for full '{crit_ln_q}'). LN Score: 15"))
                    else:
                        logger.info(LOG_INFO.format(f"{log_prefix}   LN full match: NO ('{claim_ln_clean}' vs regex for full '{crit_ln_q}'). Trying parts if applicable."))

                        # Attempt 2: If full LN didn't match AND criteria LN has multiple parts
                        if ln_score_component < 15: # Check if not already a perfect match
                            crit_ln_parts = re.split(r'[\s\'\-]+', crit_ln_q) # Escaped hyphen and apostrophe for regex split
                            crit_ln_parts = [part for part in crit_ln_parts if part] 
                            
                            if len(crit_ln_parts) > 1:
                                logger.info(LOG_INFO.format(f"{log_prefix}     Criteria LN '{crit_ln_q}' has multiple parts: {crit_ln_parts}. Attempting match with each part against claim LN '{claim_ln_clean}'."))
                                for part in crit_ln_parts:
                                    if not part: continue 
                                    part_ln_regex_pattern = ClaimMatcher._build_regex_for_name_part(part)
                                    if self._get_compiled_regex(part_ln_regex_pattern).search(claim_ln_clean):
                                        ln_score_component = 15 
                                        logger.info(LOG_INFO.format(f"{log_prefix}       LN partial match: SUCCESS. Claim LN '{claim_ln_clean}' matched criteria part '{part}' (from '{crit_ln_q}'). LN Score set to 15."))
                                        break 
                                    else:
                                        logger.info(LOG_INFO.format(f"{log_prefix}       LN partial match: FAIL. Claim LN '{claim_ln_clean}' did not match criteria part '{part}' (pattern: '{part_ln_regex_pattern}')."))
                                if ln_score_component < 15: 
                                    logger.info(LOG_INFO.format(f"{log_prefix}     LN partial match: All parts of criteria LN '{crit_ln_q}' failed to match claim LN '{claim_ln_clean}'. LN Score remains {ln_score_component}"))
                        
                        # ENHANCED: Use comprehensive similarity analysis
                        if ln_score_component == 0:
                            # Use enhanced similarity calculation that handles OCR errors, truncation, etc.
                            similarity_result = ClaimMatcher.calculate_enhanced_similarity(crit_ln_q, claim_ln_clean)
                            
                            if similarity_result['score'] > 0:
                                ln_score_component = similarity_result['score']
                                logger.info(LOG_INFO.format(f"{log_prefix}     LN Enhanced match: '{claim_ln_clean}' vs '{crit_ln_q}' → {similarity_result['match_type']} ({similarity_result['similarity']*100:.1f}% similarity). Awarding LN Score: {ln_score_component}"))
                            else:
                                logger.info(LOG_INFO.format(f"{log_prefix}     LN Enhanced match: No sufficient similarity found between '{claim_ln_clean}' and '{crit_ln_q}' ({similarity_result['match_type']})."))
                except re.error as e:
                    logger.error(LOG_ERROR.format(f"{log_prefix} Regex error during LN scoring: {e}. Query LN: '{crit_ln_q}'. Pattern: '{full_ln_regex_pattern if 'full_ln_regex_pattern' in locals() else (part_ln_regex_pattern if 'part_ln_regex_pattern' in locals() else 'N/A')}'. LN Score set to 0."))
                    ln_score_component = 0
            
            if ln_score_component == 0 and claim_ln_clean : 
                 logger.info(LOG_INFO.format(f"{log_prefix}   LN match: FINAL. Claim LN '{claim_ln_clean}' did not match criteria '{crit_ln_q}' (full or parts). LN Score: 0"))
        else:  # No criteria last name provided
            if fn_score_component == 15: 
                ln_score_component = 15 
                logger.info(LOG_INFO.format(f"{log_prefix}   LN: No criteria LN provided. FN matched, so awarding 15 for LN component."))

        total_score = fn_score_component + ln_score_component
        logger.info(LOG_INFO.format(f"{log_prefix} Final Name Score: {total_score}/30 (FN: {fn_score_component}, LN: {ln_score_component})"))
        return total_score

    def _score_api_claim_candidate(
        self,
        api_claim_data: Dict[str, Any],
        claim_procedures_from_api: List[Dict[str, Any]],
        criteria: SearchCriteria,
        claim_owner_patient_details: Dict[str, Any], # Patient details (FName, LName) for the claim's PatNum
        log_prefix: str = ""
    ) -> tuple[int, bool, str]:  # Returns (score, used_alternate_benefit_override, override_type)
        """
        Scores a potential API claim against search criteria. Max score 100.
        - Date: Exact match (30 points)
        - Status: Exact match 'S' or 'H' (10 points)
        - Name: >65% match (actual score from _calculate_name_match_score, max 30 points)
        - Procedures: >75% match (30 points)
        Returns tuple of (total score, alternate_benefit_used_flag, override_type), or (0, False, '') if critical mismatches.
        """
        current_score = 0
        used_alternate_benefit = False
        override_type = ''
        # print(f"{log_prefix} Scoring API ClaimNum: {api_claim_data.get('ClaimNum')}")
        logger.info(LOG_INFO.format(f"{log_prefix} Scoring API ClaimNum: {api_claim_data.get('ClaimNum')}"))

        # 1. Date Match (Exact Match Required)
        try:
            claim_date_obj = datetime.strptime(api_claim_data.get('DateService', ''), '%Y-%m-%d').date()
            target_date_obj = datetime.strptime(criteria.date_of_service, '%Y-%m-%d').date()
            if claim_date_obj == target_date_obj:
                # current_score += 30 # Points awarded later if all checks pass
                logger.info(LOG_INFO.format(f"{log_prefix}  Date: PASS (Match: {claim_date_obj})"))
            else:
                logger.warning(LOG_WARNING.format(f"{log_prefix}  Date: FAIL (Mismatch: Claim {claim_date_obj} vs Target {target_date_obj}). Critical mismatch, returning 0."))
                return 0, False, '' # Critical mismatch
        except ValueError:
                logger.error(LOG_ERROR.format(f"{log_prefix}  Date: FAIL (Invalid date format for claim {api_claim_data.get('ClaimNum')} or criteria). Critical mismatch, returning 0."))
                return 0, False, ''

        # 2. Status Match (Exact Match 'S' or 'H' Required)
        claim_status = api_claim_data.get('ClaimStatus')
        if claim_status in ['S', 'H']:
            # current_score += 10 # Points awarded later
            logger.info(LOG_INFO.format(f"{log_prefix}  Status: PASS (Status: {claim_status})"))
        else:
            logger.warning(LOG_WARNING.format(f"{log_prefix}  Status: FAIL (Status: {claim_status} not S or H). Critical mismatch, returning 0."))
            return 0, False, '' # Critical mismatch

        # 3. Name Match (Must be >65%, i.e., score >= 20 out of 30)
        # Use full names from criteria for matching. _calculate_name_match_score handles multi-part names.
        crit_patient_fn_full = criteria.patient_first_name # Full first name from criteria
        crit_patient_ln_full = criteria.patient_last_name   # Full last name from criteria

        claim_owner_fn = claim_owner_patient_details.get('FName')
        claim_owner_ln = claim_owner_patient_details.get('LName')

        name_score = self._calculate_name_match_score_with_nicknames(
            claim_patient_fn=claim_owner_fn,
            claim_patient_ln=claim_owner_ln,
            criteria_patient_fn_query=crit_patient_fn_full, # Pass full name
            criteria_patient_ln_query=crit_patient_ln_full, # Pass full name
            log_prefix=f"{log_prefix}    "
        )
        
        # FALLBACK: If initial name matching fails, try swapping first and last name
        if name_score < 20:
            logger.info(LOG_INFO.format(f"{log_prefix}  Name: FAIL (Score: {name_score}/30). Attempting name swap fallback..."))
            
            # Try swapping the criteria names (patient's first and last name)
            swapped_criteria_fn = crit_patient_ln_full
            swapped_criteria_ln = crit_patient_fn_full
            
            swapped_name_score = self._calculate_name_match_score_with_nicknames(
                claim_patient_fn=claim_owner_fn,
                claim_patient_ln=claim_owner_ln,
                criteria_patient_fn_query=swapped_criteria_fn,  # Swapped: last name as first
                criteria_patient_ln_query=swapped_criteria_ln,  # Swapped: first name as last
                log_prefix=f"{log_prefix}    [NameSwap] " # Indent for sub-logging with swap indicator
            )
            
            if swapped_name_score >= 20:
                name_score = swapped_name_score
                logger.info(LOG_SUCCESS.format(f"{log_prefix}  Name: PASS via SWAP (Score: {name_score}/30). Original: '{crit_patient_fn_full} {crit_patient_ln_full}' -> Swapped: '{swapped_criteria_fn} {swapped_criteria_ln}'"))
            else:
                logger.warning(LOG_WARNING.format(f"{log_prefix}  Name: FAIL via SWAP (Score: {swapped_name_score}/30). Both original and swapped attempts failed. Critical mismatch, returning 0."))
                return 0, False, ''
        else:
            logger.info(LOG_INFO.format(f"{log_prefix}  Name: PASS (Score: {name_score}/30. Claim Owner: '{claim_owner_fn} {claim_owner_ln}' vs Criteria: '{crit_patient_fn_full} {crit_patient_ln_full}')"))


        # 4. Procedure Match (Must be >75%)
        procedure_match_percentage = 0.0
        if criteria.payment_info and criteria.payment_info.procedures and claim_procedures_from_api:
            payment_proc_codes_normalized = [p.proc_code for p in criteria.payment_info.procedures] # Already normalized
            
            api_claim_proc_codes_normalized = [
                self.normalize_procedure_code(proc.get('CodeSent', '')) for proc in claim_procedures_from_api
            ]
            
            if not payment_proc_codes_normalized and not api_claim_proc_codes_normalized: # Both empty
                procedure_match_percentage = 1.0 # Perfect match if no procs expected and no procs found
            elif payment_proc_codes_normalized and not api_claim_proc_codes_normalized: # EOB has procs, but claim does not
                 # This case could be debatable. If EOB has no procs, should claim having procs be a mismatch?
                 # For now, let's consider it a mismatch if the goal is to find an exact counterpart.
                 # If the goal was "find a claim that *could* be related", this might be acceptable.
                 # Given "100% confidence" goal, treating as mismatch.
                procedure_match_percentage = 0.0
            elif not payment_proc_codes_normalized and api_claim_proc_codes_normalized: # EOB has no procs, but claim does
                 # This case could be debatable. If EOB has no procs, should claim having procs be a mismatch?
                 # For now, let's consider it a mismatch if the goal is to find an exact counterpart.
                 # If the goal was "find a claim that *could* be related", this might be acceptable.
                 # Given "100% confidence" goal, treating as mismatch.
                procedure_match_percentage = 0.0
            else: # Both have procedures
                proc_match_details = self._match_procedure_codes(payment_proc_codes_normalized, api_claim_proc_codes_normalized)
                procedure_match_percentage = proc_match_details.get('match_percentage', 0.0)
            
            if procedure_match_percentage > 0.49:
                # current_score += 30 # Points awarded later
                logger.info(LOG_INFO.format(f"{log_prefix}  Procedures: PASS (Match %: {procedure_match_percentage*100:.2f}% > 49%. EOB Procs Cnt: {len(payment_proc_codes_normalized)}, Claim Procs Cnt: {len(api_claim_proc_codes_normalized)})"))
            else:
                # Check for alternate benefit override if procedure codes don't match
                payment_total = sum(p.amount_paid for p in criteria.payment_info.procedures) if criteria.payment_info and criteria.payment_info.procedures else 0.0
                claim_fee_value = float(api_claim_data.get('ClaimFee', 0))
                
                if self._has_strong_non_procedure_match_with_fees(
                    claim_date_obj=claim_date_obj,
                    target_date_obj=target_date_obj,
                    name_score=name_score,
                    claim_procedures=claim_procedures_from_api,  # API procedures with FeeBilled
                    eob_procedures=criteria.payment_info.procedures,  # EOB procedures with submitted_amt
                    log_prefix=f"{log_prefix}    [AlternateBenefit] "
                ):
                    used_alternate_benefit = True
                    override_type = 'fee_match'
                    logger.info(LOG_INFO.format(f"{log_prefix}  Procedures: ALTERNATE BENEFIT OVERRIDE (Enhanced fee matching overrides {procedure_match_percentage*100:.2f}% proc match)"))
                elif self._has_procedure_count_match(
                    claim_date_obj=claim_date_obj,
                    target_date_obj=target_date_obj,
                    name_score=name_score,
                    claim_procedures=claim_procedures_from_api,  # API procedures
                    eob_procedures=criteria.payment_info.procedures,  # EOB procedures
                    log_prefix=f"{log_prefix}    [CountMatch] "
                ):
                    used_alternate_benefit = True
                    override_type = 'count_match'
                    logger.info(LOG_INFO.format(f"{log_prefix}  Procedures: COUNT MATCH OVERRIDE (Procedure count matching overrides {procedure_match_percentage*100:.2f}% proc match)"))
                else:
                    logger.warning(LOG_WARNING.format(f"{log_prefix}  Procedures: FAIL (Match %: {procedure_match_percentage*100:.2f}% <= 49%. EOB Procs Cnt: {len(payment_proc_codes_normalized)}, Claim Procs Cnt: {len(api_claim_proc_codes_normalized)}). Critical mismatch, returning 0."))
                    return 0, False, ''
        elif not (criteria.payment_info and criteria.payment_info.procedures) and not claim_procedures_from_api: # No procedures on EOB criteria and no procedures on API claim
            # current_score += 30 # Perfect proc score
            logger.info(LOG_INFO.format(f"{log_prefix}  Procedures: PASS (No procedures on EOB criteria and no procedures on API claim)"))
        elif not (criteria.payment_info and criteria.payment_info.procedures) and claim_procedures_from_api: # No procedures on EOB criteria, but API claim has them
            logger.warning(LOG_WARNING.format(f"{log_prefix}  Procedures: FAIL (No EOB procs, but API claim has {len(claim_procedures_from_api)} procs). Critical mismatch, returning 0."))
            return 0, False, ''
        elif (criteria.payment_info and criteria.payment_info.procedures) and not claim_procedures_from_api: # Procedures on EOB criteria, but API claim has none
            logger.warning(LOG_WARNING.format(f"{log_prefix}  Procedures: FAIL (EOB has {len(criteria.payment_info.procedures)} procs, but API claim has no procs). Critical mismatch, returning 0."))
            return 0, False, ''
        # else: one has procs, other doesn't - already handled by procedure_match_percentage calculation if both had lists (one empty)

        # All checks passed, calculate final score
        # Date: 30, Status: 10, Procedures: 30. Name: variable (name_score)
        current_score = 30 + 10 + name_score + 30
        
        logger.info(LOG_SUCCESS.format(f"{log_prefix}  ALL CHECKS PASSED. FINAL SCORE for ClaimNum {api_claim_data.get('ClaimNum')}: {current_score}"))
        return current_score, used_alternate_benefit, override_type

    def _check_secondary_insurance(self, claim: Dict) -> bool:
        has_secondary_plan_initial = int(claim.get('InsSubNum2', 0)) > 0 or int(claim.get('PlanNum2', 0)) > 0
        has_secondary_plan = has_secondary_plan_initial
        
        if has_secondary_plan_initial:
            pat_num = claim.get('PatNum')
            if pat_num:
                try:
                    print(f"    Double checking plans for PatNum={pat_num} via /patplans")
                    pat_plans = self.make_request(f"patplans?PatNum={pat_num}")
                    if isinstance(pat_plans, list):
                        print(f"    /patplans response: {len(pat_plans)} plan(s) found")
                        if len(pat_plans) <= 1:
                            print(f"    Overriding has_secondary_plan to False based on /patplans check.")
                            has_secondary_plan = False
                        else:
                            print(f"    Confirmed multiple plans via /patplans.")
                    else:
                        print(f"    Warning: Unexpected response format from /patplans: {type(pat_plans)}")
                except Exception as patplan_err:
                    print(f"    Warning: Error calling /patplans endpoint: {patplan_err}")
            else:
                print(f"    Warning: PatNum not found in claim data, cannot double check /patplans.")
        
        return has_secondary_plan

    def _get_entity_data(self, last_name: str, first_name: str, entity_type: str = "patient") -> Dict[str, Any]:
        try:
            is_patient = entity_type.lower() == "patient"
            entity_label = "patient" if is_patient else "subscriber"
            
            # Add early exit if essential name parts are missing
            if not first_name or not first_name.strip() or not last_name or not last_name.strip():
                logger.warning(LOG_WARNING.format(f"  [{entity_label} API Query via ClaimMatcher] Missing or empty first_name ('{first_name}') or last_name ('{last_name}'). Aborting _get_entity_data."))
                return {}

            initial_entities = []
            
            # Attempt 1: Query with the full last name and first name
            logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] Initial attempt: LName='{last_name}', FName='{first_name}', PatStatus='Patient'"))
            initial_entities = self.make_request(f"patients/Simple?LName={last_name}&FName={first_name}&PatStatus=Patient")
            
            # Attempt 2: If no results and last_name has multiple parts, try each part
            if not initial_entities and first_name:
                # Split last name by common delimiters (space, hyphen, apostrophe)
                last_name_parts = re.split(r'[\s\'\-]+', last_name)
                last_name_parts = [part for part in last_name_parts if part and len(part) > 1] # Use parts with more than 1 char

                if len(last_name_parts) > 1: # Only if there are multiple valid parts
                    logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] Initial attempt failed for full LName '{last_name}'. Trying parts: {last_name_parts}"))
                    for part_ln in last_name_parts:
                        logger.info(LOG_INFO.format(f"    Attempting with LName part: '{part_ln}', FName: '{first_name}'"))
                        entities_from_part = self.make_request(f"patients/Simple?LName={part_ln}&FName={first_name}&PatStatus=Patient")
                        if entities_from_part: # If any part yields a result with the first name
                            logger.info(LOG_INFO.format(f"      SUCCESS: Found {len(entities_from_part)} {entity_label}(s) using LName part '{part_ln}'. Using these results."))
                            initial_entities = entities_from_part
                            break # Use the first successful partial last name match
                    if not initial_entities:
                        logger.info(LOG_INFO.format(f"    All LName parts failed to find a match with FName '{first_name}'."))
            
            entities_to_process = initial_entities

            # Attempt 3: If still no entities, try last name only search (existing fallback)
            if not entities_to_process and first_name: # first_name check ensures we have something to filter by later
                logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] No exact or partial LName match with FName found. Trying full last name '{last_name}' only search."))
                all_last_name_entities = self.make_request(f"patients/Simple?LName={last_name}&PatStatus=Patient")
                
                if all_last_name_entities:
                    logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] Found {len(all_last_name_entities)} {entity_label}(s) with full last name '{last_name}'. Filtering by FName '{first_name}'."))
                    
                    best_matches = []
                    first_name_lower = first_name.lower()
                    
                    for entity_candidate in all_last_name_entities:
                        entity_first_name = entity_candidate.get('FName', '').lower()
                        score = 0.0
                        
                        # Prioritize exact match or startsWith for first name in this fallback
                        if entity_first_name == first_name_lower:
                            score = 1.0
                        elif entity_first_name.startswith(first_name_lower):
                            score = 0.9
                        elif first_name_lower.startswith(entity_first_name):
                            score = 0.8
                        else: # Fallback to Levenshtein for more distant matches if necessary
                            distance = ClaimMatcher.levenshtein_distance(entity_first_name, first_name_lower)
                            max_len = max(len(entity_first_name), len(first_name_lower))
                            if max_len > 0:
                                similarity = 1.0 - (distance / max_len)
                                if similarity >= 0.6: # Threshold for considering a Levenshtein match
                                    score = similarity * 0.7 # Weight Levenshtein matches lower than direct/prefix
                        
                        if score > 0.75: # Stricter threshold for selecting from last-name-only list
                            best_matches.append({"entity": entity_candidate, "score": score})
                            logger.info(LOG_INFO.format(f"    Potential FName match: '{entity_candidate.get('FName')}' vs '{first_name}' (Score: {score:.2f})"))
                    
                    if best_matches:
                        best_matches = sorted(best_matches, key=lambda x: x["score"], reverse=True)
                        # Select the top match if its score is high enough and significantly better than the next
                        if best_matches[0]["score"] >= 0.70: # High confidence in this filtered match
                            if len(best_matches) == 1 or best_matches[0]["score"] > best_matches[1]["score"] + 0.1: # Reasonably unambiguous
                                entities_to_process = [best_matches[0]["entity"]]
                                logger.info(LOG_INFO.format(f"    Selected best FName match from LName-only search: {entities_to_process[0]['FName']} {entities_to_process[0]['LName']} (Score: {best_matches[0]['score']:.2f})"))
                            else:
                                logger.warning(LOG_WARNING.format(f"    Ambiguous FName match from LName-only search. Top: {best_matches[0]['entity']['FName']} ({best_matches[0]['score']:.2f}), Next: {best_matches[1]['entity']['FName']} ({best_matches[1]['score']:.2f}). Discarding due to ambiguity."))
                                entities_to_process = [] # Ambiguous
                        else:
                            logger.info(LOG_INFO.format(f"    Best FName match '{best_matches[0]['entity']['FName']}' score {best_matches[0]['score']:.2f} not high enough or too ambiguous. Discarding LName-only results."))
                            entities_to_process = [] # Not confident enough
                else:
                    logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] LName-only search for '{last_name}' also yielded no results."))
            
            # Attempt 4: If still no entities (e.g. compound LName like "De La Cruz" didn't match as parts or full)
            # and the original last_name had multiple parts, try the *last* part of the original last_name as a final attempt.
            # This handles cases like "Navarro Cedillo" where "Cedillo" might be the primary stored LN.
            if not entities_to_process and first_name:
                original_last_name_parts = re.split(r'[\s\'\-]+', last_name) # original last_name from input
                original_last_name_parts = [part for part in original_last_name_parts if part and len(part) > 1]
                if len(original_last_name_parts) > 1:
                    last_part_of_original_ln = original_last_name_parts[-1]
                    if last_part_of_original_ln.lower() not in [p.lower() for p in last_name_parts]: # Ensure we haven't tried this exact part
                        logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] Final attempt: Using last part of original LName '{last_part_of_original_ln}' with FName '{first_name}'."))
                        entities_from_last_part = self.make_request(f"patients/Simple?LName={last_part_of_original_ln}&FName={first_name}&PatStatus=Patient")
                        if entities_from_last_part:
                            logger.info(LOG_INFO.format(f"    SUCCESS: Found {len(entities_from_last_part)} {entity_label}(s) using last LName part '{last_part_of_original_ln}'. Using these results."))
                            entities_to_process = entities_from_last_part
                        else:
                             logger.info(LOG_INFO.format(f"    Last part LName search for '{last_part_of_original_ln}' also yielded no results."))

            if not entities_to_process:
                logger.info(LOG_WARNING.format(f"  [{entity_label} API Query via ClaimMatcher] RESULT: No matching {entity_label}s found after all attempts for LName '{last_name}', FName '{first_name}'."))
                return {}
            
            # Process the first entity from the successful search attempt
            entity = entities_to_process[0] 
            logger.info(LOG_SUCCESS.format(f"  [{entity_label} API Query via ClaimMatcher] RESULT: Selected {entity_label} - PatNum={entity['PatNum']}, Name='{entity.get('FName', '')} {entity.get('LName', '')}', Status='{entity.get('PatStatus', '')}'"))

            if is_patient:
                logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] Querying claims for PatNum={entity['PatNum']}"))
                claims = self.make_request(f"claims?PatNum={entity['PatNum']}")
                logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] RESULT: Found {len(claims)} claims"))
                
                return {
                    'patient': entity,
                    'claims': claims
                }
            else: # subscriber
                logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] Querying subscriptions for Subscriber={entity['PatNum']}"))
                inssubs = self.make_request(f"inssubs?Subscriber={entity['PatNum']}")
                logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] RESULT: Found {len(inssubs)} insurance subscriptions"))
                
                if not inssubs:
                    return {
                        'subscriber': entity,
                        'inssubs': None
                    }
                
                active_inssub = next(
                    (sub for sub in inssubs 
                    if sub['DateTerm'] == "0001-01-01"
                    or datetime.strptime(sub['DateTerm'], '%Y-%m-%d').date() > datetime.now().date()),
                    inssubs[0] if inssubs else None
                )
                
                if active_inssub:
                    logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] DETAIL: Active subscription found - InsSubNum={active_inssub['InsSubNum']}"))
                else:
                    logger.info(LOG_INFO.format(f"  [{entity_label} API Query via ClaimMatcher] DETAIL: No active subscription found, using first one if available."))
            
                return {
                    'subscriber': entity,
                    'inssubs': active_inssub
                }
                
        except Exception as e:
            logger.error(LOG_ERROR.format(f"  [{entity_label} API Query via ClaimMatcher] ERROR: {str(e)}"))
            return {}

    def filter_cached_claims(self, criteria: SearchCriteria, claims_data: Dict[str, Any]) -> list[ClaimMatch]:
        log_prefix = f"[DB Match via ClaimMatcher: {criteria.patient_first_name or 'N/A'} {criteria.patient_last_name or 'N/A'} (Sub: {criteria.subscriber_first_name or 'N/A'} {criteria.subscriber_last_name or 'N/A'})]"
        
        logger.info("") # Newline
        logger.info(LOG_SECTION_START.format("DB MATCHING PROCESS - STRICT THRESHOLDS"))
        # Log initial criteria based on what might be available
        logger.info(LOG_INFO.format(f"Criteria Patient: {criteria.patient_first_name or 'N/A'} {criteria.patient_last_name or 'N/A'}"))
        logger.info(LOG_INFO.format(f"Criteria Subscriber: {criteria.subscriber_first_name or 'N/A'} {criteria.subscriber_last_name or 'N/A'}"))
        logger.info(LOG_INFO.format(f"Criteria Date of Service: {criteria.date_of_service}"))
        
        db_claims = claims_data.get('claims', [])
        if not db_claims:
            logger.warning(LOG_WARNING.format("No claims found in the provided claims_data for DB matching."))
            logger.info(LOG_SECTION_END.format("DB MATCHING PROCESS - STRICT THRESHOLDS COMPLETED"))
            return []

        potential_matches = []
        target_date_obj: Optional[date] = None
        try:
            target_date_obj = datetime.strptime(criteria.date_of_service, '%Y-%m-%d').date()
        except ValueError:
            logger.error(LOG_ERROR.format(f"Invalid date format in search criteria: {criteria.date_of_service}. Cannot perform DB search."))
            logger.info(LOG_SECTION_END.format("DB MATCHING PROCESS - STRICT THRESHOLDS COMPLETED"))
            return []

        # Determine which name from criteria to use for matching against cached claim's patient name
        criteria_name_fn_to_use = None
        criteria_name_ln_to_use = None
        criteria_name_source_for_log = ""

        if criteria.patient_first_name and criteria.patient_first_name.strip() and \
           criteria.patient_last_name and criteria.patient_last_name.strip():
            criteria_name_fn_to_use = criteria.patient_first_name
            criteria_name_ln_to_use = criteria.patient_last_name
            criteria_name_source_for_log = "Patient"
            logger.info(LOG_INFO.format(f"{log_prefix} Using {criteria_name_source_for_log} Name from criteria for cache matching: '{criteria_name_fn_to_use} {criteria_name_ln_to_use}'"))
        elif criteria.subscriber_first_name and criteria.subscriber_first_name.strip() and \
             criteria.subscriber_last_name and criteria.subscriber_last_name.strip():
            criteria_name_fn_to_use = criteria.subscriber_first_name
            criteria_name_ln_to_use = criteria.subscriber_last_name
            criteria_name_source_for_log = "Subscriber (as Patient)"
            logger.info(LOG_INFO.format(f"{log_prefix} Criteria Patient Name missing/empty. Using {criteria_name_source_for_log} Name from criteria for cache matching against cached Patient Name: '{criteria_name_fn_to_use} {criteria_name_ln_to_use}'"))
        else:
            logger.warning(LOG_WARNING.format(f"{log_prefix} Neither Patient nor Subscriber name sufficiently provided in criteria. Cannot perform effective name matching for cached claims."))
            logger.info(LOG_SECTION_END.format("DB MATCHING PROCESS - STRICT THRESHOLDS COMPLETED (No criteria name for cache match)"))
            return []
        
        logger.info(LOG_INFO.format(f"Evaluating {len(db_claims)} claims from database cache using strict thresholds (matching against criteria's {criteria_name_source_for_log} Name)."))

        # Normalize EOB procedure codes once
        payment_proc_codes_normalized = [self.normalize_procedure_code(p.proc_code) for p in criteria.payment_info.procedures if p.proc_code]
        
        logger.info(LOG_INFO.format(f"EOB Procedure Codes (Normalized): {payment_proc_codes_normalized}"))
        # logger.info(LOG_INFO.format(f"Search Criteria - Patient: '{crit_patient_fn_full} {crit_patient_ln_full}'")) # Original line, crit_patient_fn_full not defined here anymore
        # Updated log line to show which criteria name is being used:
        logger.info(LOG_INFO.format(f"Name matching in cache will use Criteria {criteria_name_source_for_log} Name: '{criteria_name_fn_to_use} {criteria_name_ln_to_use}'"))

        claims_evaluated = 0
        date_skips = 0
        status_skips = 0
        name_skips = 0
        procedure_skips = 0
        missing_data_skips = 0
        
        for claim in db_claims:
            claims_evaluated += 1
            claim_num_for_log = claim.get('claim_num') or claim.get('ClaimNum', 'UnknownDBClaimNum')
            current_log_prefix = f"{log_prefix} [CacheClaim#{claim_num_for_log}]"

            # 1. DATE SCORING (Exact Match Required)
            claim_date_str = claim.get('date_of_service') or claim.get('claim_date') or claim.get('DateService')
            if not claim_date_str:
                missing_data_skips += 1
                continue
            try:
                claim_date_obj = datetime.strptime(claim_date_str, '%Y-%m-%d').date()
                if claim_date_obj != target_date_obj:
                    date_skips += 1
                    continue
                logger.info(LOG_INFO.format(f"{current_log_prefix} Date: PASS (Exact Match: {claim_date_obj})"))
            except ValueError:
                missing_data_skips += 1
                continue

            # 2. STATUS SCORING (Exact Match 'S' or 'H' Required, or 'R' with matching Secondary)
            # Note: Cached claims might not always have 'ClaimStatus' in the same way API claims do.
            # We'll check for 'claim_status' or 'ClaimStatus'. Adjust if your cache uses different keys.
            claim_status = claim.get('claim_status') or claim.get('ClaimStatus')
            
            if claim_status in ['S', 'H']:
                logger.info(LOG_INFO.format(f"{current_log_prefix} Status: PASS (Status: {claim_status})"))
            elif claim_status == 'R':
                # For 'R' status, only allow Primary claims (not secondary)
                is_secondary = claim.get('is_secondary', claim.get('IsSecondary', False))
                if isinstance(is_secondary, str):
                    is_secondary = is_secondary.lower() == 'true'
                
                if not is_secondary:  # Primary claim
                    logger.info(LOG_INFO.format(f"{current_log_prefix} Status: PASS (Status: R, Primary claim - is_secondary={is_secondary})"))
                else:
                    # Secondary claim with 'R' status - skip
                    logger.info(LOG_INFO.format(f"{current_log_prefix} Status: FAIL (Status: R but is a Secondary claim)"))
                    status_skips += 1
                    continue
            else:
                status_skips += 1
                continue

            # 3. NAME SCORING (Must be >65%, i.e., score >= 20 out of 30)
            # Cached claim patient names might be under keys like 'patient_first_name', 'pat_fn', etc.
            patient_fn_raw = claim.get('patient_first_name') or claim.get('pat_fn')
            patient_ln_raw = claim.get('patient_last_name') or claim.get('pat_ln')

            if not patient_fn_raw or not patient_ln_raw: # Both first and last name must be present in cache
                missing_data_skips += 1
                continue

            # Initial name matching attempt
            name_score = self._calculate_name_match_score_with_nicknames(
                claim_patient_fn=patient_fn_raw,          # This is from the cache claim (e.g., pat_fn)
                claim_patient_ln=patient_ln_raw,          # This is from the cache claim (e.g., pat_ln) - CORRECTED
                criteria_patient_fn_query=criteria_name_fn_to_use, # Name from criteria (either patient or subscriber)
                criteria_patient_ln_query=criteria_name_ln_to_use, # Name from criteria (either patient or subscriber)
                log_prefix=f"{current_log_prefix}    " # Indent for sub-logging
            )
            
            # FALLBACK: If initial name matching fails, try swapping first and last name
            if name_score < 20:
                logger.info(LOG_INFO.format(f"{current_log_prefix} Name: FAIL (Score: {name_score}/30). Attempting name swap fallback..."))
                
                # Try swapping the criteria names (patient's first and last name)
                swapped_criteria_fn = criteria_name_ln_to_use
                swapped_criteria_ln = criteria_name_fn_to_use
                
                swapped_name_score = self._calculate_name_match_score_with_nicknames(
                    claim_patient_fn=patient_fn_raw,
                    claim_patient_ln=patient_ln_raw,
                    criteria_patient_fn_query=swapped_criteria_fn,  # Swapped: last name as first
                    criteria_patient_ln_query=swapped_criteria_ln,  # Swapped: first name as last
                    log_prefix=f"{current_log_prefix}    [NameSwap] " # Indent for sub-logging with swap indicator
                )
                
                if swapped_name_score >= 20:
                    name_score = swapped_name_score
                    logger.info(LOG_SUCCESS.format(f"{current_log_prefix} Name: PASS via SWAP (Score: {name_score}/30). Original: '{criteria_name_fn_to_use} {criteria_name_ln_to_use}' -> Swapped: '{swapped_criteria_fn} {swapped_criteria_ln}'"))
                else:
                    logger.info(LOG_INFO.format(f"{current_log_prefix} Name: FAIL via SWAP (Score: {swapped_name_score}/30). Both original and swapped attempts failed."))
                    name_skips += 1
                    continue
            else:
                logger.info(LOG_INFO.format(f"{current_log_prefix} Name: PASS (Score: {name_score}/30)"))


            # 4. PROCEDURE SCORING (Must be >75%)
            db_claim_proc_codes_normalized = []
            # Cached procedures might be under 'procedures', 'claim_procs', etc.
            # And procedure codes themselves under 'proc_code', 'code', 'CodeSent'
            cached_procs_list = claim.get('procedures', claim.get('claim_procs', []))
            for proc_item in cached_procs_list:
                code = proc_item.get('proc_code') or proc_item.get('code') or proc_item.get('CodeSent')
                if code:
                    db_claim_proc_codes_normalized.append(self.normalize_procedure_code(code))

            procedure_match_percentage = 0.0
            alternate_benefit_override = False
            
            if not payment_proc_codes_normalized and not db_claim_proc_codes_normalized: # Both empty
                procedure_match_percentage = 1.0
            elif payment_proc_codes_normalized and not db_claim_proc_codes_normalized:
                procedure_match_percentage = 0.0
            elif not payment_proc_codes_normalized and db_claim_proc_codes_normalized:
                procedure_match_percentage = 0.0 # EOB has no procs, but cache claim does
            else: # Both have procedures
                proc_match_details = self._match_procedure_codes(payment_proc_codes_normalized, db_claim_proc_codes_normalized)
                procedure_match_percentage = proc_match_details.get('match_percentage', 0.0)

            # Check for alternate benefit override if procedure codes don't match
            if procedure_match_percentage <= 0.49:
                # Check if this could be an alternate benefit scenario using enhanced fee-based matching
                if self._has_strong_non_procedure_match_with_fees(
                    claim_date_obj=claim_date_obj,
                    target_date_obj=target_date_obj,
                    name_score=name_score,
                    claim_procedures=cached_procs_list,  # Database procedures with fee_billed
                    eob_procedures=criteria.payment_info.procedures,  # EOB procedures with submitted_amt
                    log_prefix=f"{current_log_prefix}    [AlternateBenefit] "
                ):
                    alternate_benefit_override = True
                    logger.info(LOG_INFO.format(f"{current_log_prefix} Procedures: ALTERNATE BENEFIT OVERRIDE (Enhanced fee matching overrides {procedure_match_percentage*100:.2f}% proc match)"))
                elif self._has_procedure_count_match(
                    claim_date_obj=claim_date_obj,
                    target_date_obj=target_date_obj,
                    name_score=name_score,
                    claim_procedures=cached_procs_list,  # Database procedures
                    eob_procedures=criteria.payment_info.procedures,  # EOB procedures
                    log_prefix=f"{current_log_prefix}    [CountMatch] "
                ):
                    alternate_benefit_override = True
                    logger.info(LOG_INFO.format(f"{current_log_prefix} Procedures: COUNT MATCH OVERRIDE (Procedure count matching overrides {procedure_match_percentage*100:.2f}% proc match)"))
                else:
                    procedure_skips += 1
                    continue
            else:
                logger.info(LOG_INFO.format(f"{current_log_prefix} Procedures: PASS (Match %: {procedure_match_percentage*100:.2f}% > 49%)"))

            # ALL CHECKS PASSED - This is a confident match (based on primary name match)
            logger.info(LOG_SUCCESS.format(f"{current_log_prefix} ALL PRIMARY CHECKS PASSED. Calculating score and checking subscriber if applicable."))
            
            subscriber_bonus_points = 0
            if criteria.subscriber_first_name and criteria.subscriber_first_name.strip() and \
               criteria.subscriber_last_name and criteria.subscriber_last_name.strip():
                
                cached_claim_sub_fn = claim.get('subscriber_first_name') 
                cached_claim_sub_ln = claim.get('subscriber_last_name')

                if cached_claim_sub_fn and cached_claim_sub_fn.strip() and \
                   cached_claim_sub_ln and cached_claim_sub_ln.strip():
                    
                    sub_name_score_value = self._calculate_name_match_score_with_nicknames(
                        claim_patient_fn=cached_claim_sub_fn.strip(), # from cached claim's subscriber fields
                        claim_patient_ln=cached_claim_sub_ln.strip(), # from cached claim's subscriber fields
                        criteria_patient_fn_query=criteria.subscriber_first_name, # from criteria's subscriber fields
                        criteria_patient_ln_query=criteria.subscriber_last_name,  # from criteria's subscriber fields
                        log_prefix=f"{current_log_prefix}    [SubMatch] "
                    )
                    
                    if sub_name_score_value == 30: # Perfect subscriber F+L match
                        subscriber_bonus_points = 15
                        logger.info(LOG_INFO.format(f"{current_log_prefix}    Subscriber Name: FULL MATCH. Bonus: +{subscriber_bonus_points}"))
                    elif sub_name_score_value >= 15: # Partial subscriber F or L match (score includes at least one full name part)
                        subscriber_bonus_points = 8 
                        logger.info(LOG_INFO.format(f"{current_log_prefix}    Subscriber Name: PARTIAL MATCH (Score {sub_name_score_value}). Bonus: +{subscriber_bonus_points}"))
                    else:
                        logger.info(LOG_INFO.format(f"{current_log_prefix}    Subscriber Name: NO MATCH (Score {sub_name_score_value}). No bonus."))
                else:
                    logger.info(LOG_INFO.format(f"{current_log_prefix}    Subscriber Name: Cached claim missing subscriber name details. No bonus check."))
            else:
                logger.info(LOG_INFO.format(f"{current_log_prefix}    Subscriber Name: Criteria missing subscriber name details. No bonus check."))

            # Construct claim_procs for the ClaimMatch object, ensuring correct structure
            # This part needs to be robust to how procedures are stored in your cache.
            # Assuming cached procs are similar to API procs or need transformation.
            claim_procs_for_match_obj = []
            for proc_data in cached_procs_list: # Use the same list as for code extraction
                code_sent = proc_data.get('proc_code') or proc_data.get('code') or proc_data.get('CodeSent')
                if not code_sent: continue # Skip procs without codes

                claim_proc_num_val = proc_data.get('claim_proc_num') or proc_data.get('ClaimProcNum')
                try:
                    claim_proc_num_int = int(claim_proc_num_val) if claim_proc_num_val is not None else 0
                except (ValueError, TypeError):
                    claim_proc_num_int = 0
                
                claim_procs_for_match_obj.append({
                    "CodeSent": self.normalize_procedure_code(code_sent),
                    "FeeBilled": float(proc_data.get('fee_billed') or proc_data.get('FeeBilled') or 0),
                    "ClaimProcNum": claim_proc_num_int,
                    "WriteOff": float(proc_data.get('writeoff') or proc_data.get('WriteOff') or 0),
                    # Add other fields if they exist in your cache and are needed for ClaimMatch
                    "InsPayAmt": float(proc_data.get('ins_pay_amt') or proc_data.get('InsPayAmt') or 0),
                    "DedApplied": float(proc_data.get('ded_applied') or proc_data.get('DedApplied') or 0),
                    "Status": proc_data.get('status') or proc_data.get('status_val') or proc_data.get('Status'), # MongoDB uses 'status'
                    "DateInsFinalized": proc_data.get('date_ins_finalized', proc_data.get('DateInsFinalized', proc_data.get('DateSuppReceived', ''))),
                    "ToothNum": proc_data.get('tooth_num') or proc_data.get('ToothNum') or '', # MongoDB uses 'tooth_num'
                    "Remarks": proc_data.get('remarks') or proc_data.get('Remarks') or '', # MongoDB uses 'remarks'
                    # Add new UCR fields from cached claims
                    "matchesUCR": proc_data.get('matchesUCR', False),
                    "ucr_amount": float(proc_data.get('ucr_amount') or 0)
                })
            
            # name_score here is the primary_name_score (patient name vs chosen criteria name)
            final_calculated_score = 30 + 10 + name_score + 30 + subscriber_bonus_points 

            # Ortho details from cached claim
            is_ortho_cached = claim.get('IsOrtho', claim.get('isOrtho'))
            is_ortho_bool = False
            if isinstance(is_ortho_cached, str):
                is_ortho_bool = is_ortho_cached.lower() == 'true'
            elif isinstance(is_ortho_cached, bool):
                is_ortho_bool = is_ortho_cached
            
            ortho_details_data = {}
            if is_ortho_bool: # If IsOrtho is true, try to get details
                ortho_details_data = claim.get('ortho_details', { # Check if details are pre-packed
                    "ortho_remain_m": claim.get('OrthoRemainM', claim.get('ortho_remain_m', 0)),
                    "ortho_date": claim.get('OrthoDate', claim.get('ortho_date', '0001-01-01')),
                    "ortho_total_m": claim.get('OrthoTotalM', claim.get('ortho_total_m', 0))
                })

            # Determine match source based on how the match was found
            match_source = 'database_strict'
            if alternate_benefit_override:
                # Check which type of override was used - this is a bit hacky but works
                # We could store the override type in a variable, but this is simpler
                if procedure_match_percentage <= 0.49:
                    # If we got here with alternate_benefit_override=True and low procedure match,
                    # it was either fee matching or count matching. We'll check count first
                    # since it's the simpler check.
                    if self._has_procedure_count_match(
                        claim_date_obj=claim_date_obj,
                        target_date_obj=target_date_obj,
                        name_score=name_score,
                        claim_procedures=cached_procs_list,
                        eob_procedures=criteria.payment_info.procedures,
                        log_prefix=f"{current_log_prefix}    [SourceCheck] "
                    ):
                        match_source = 'database_count_match'
                    else:
                        match_source = 'database_alternate_benefit'
                else:
                    match_source = 'database_alternate_benefit'

            match_obj = ClaimMatch(
                claim_num=int(claim.get('claim_num') or claim.get('ClaimNum')), # Ensure int
                pat_num=int(claim.get('pat_num') or claim.get('PatNum')),       # Ensure int
                date_of_service=claim_date_str, # Already validated
                date_sent=claim.get('DateSent'),  # Added DateSent field
                date_received=claim.get('DateReceived'),  # Added DateReceived field
                claim_fee=float(claim.get('claim_fee') or claim.get('ClaimFee') or 0),
                claim_note=claim.get('claim_note', '') or claim.get('ClaimNote', ''),
                is_secondary=claim.get('is_secondary', False) or (claim.get('plan_type') == 'S') or (claim.get('ClaimType') == 'S'),
                has_secondary_plan=claim.get('has_secondary_plan', False),
                has_pending_secondary=False, # Will be set later if primary matches alongside secondary
                match_score=final_calculated_score, # Store the calculated score
                match_source=match_source, # Indicate source and method
                claim_procs=claim_procs_for_match_obj,
                isOrtho=is_ortho_bool,
                ortho_details=ortho_details_data,
                is_supplemental=claim.get('is_supplemental', False), # If cache can indicate this
                carrier_name=claim.get('carrier_name', None), # Added to pass carrier name from matched claims
                claim_status=claim.get('claim_status', claim.get('ClaimStatus')) # Added to track claim status
            )
            potential_matches.append(match_obj)

        logger.info("") # Newline
        logger.info(LOG_SUBSECTION.format("DB STRICT THRESHOLD MATCHING STATISTICS"))
        logger.info(LOG_INFO.format(f"Total Cached Claims Evaluated: {claims_evaluated}"))
        logger.info(LOG_INFO.format(f"Claims Skipped - Date Mismatch: {date_skips}, Status: {status_skips}, Name: {name_skips}, Procedures: {procedure_skips}, Missing Data: {missing_data_skips}"))
        logger.info(LOG_INFO.format(f"Cached Claims Passing All Strict Thresholds: {len(potential_matches)}"))

        # Sort all found potential matches by score (highest first) - score is now more of a confidence sum
        sorted_potential_matches = sorted(potential_matches, key=lambda m: m['match_score'], reverse=True)
        
        final_results = []
        if sorted_potential_matches:
            # Separate into primary and secondary based on the is_secondary flag
            db_primary_matches = [m for m in sorted_potential_matches if not m['is_secondary']]
            db_secondary_matches = [m for m in sorted_potential_matches if m['is_secondary']]

            if db_primary_matches:
                if db_secondary_matches:
                    logger.info(LOG_INFO.format("DB matches (strict) include primary and secondary types. Flagging primaries with 'has_pending_secondary'."))
                    for p_match in db_primary_matches:
                        p_match['has_pending_secondary'] = True
                    # Return both primary and secondary claims when both are found
                    final_results = db_primary_matches + db_secondary_matches
                    logger.info(LOG_INFO.format(f"Returning both primary and secondary claims ({len(final_results)} total)."))
                else:
                    final_results = db_primary_matches
            elif db_secondary_matches:
                final_results = db_secondary_matches
        
        if not final_results:
            logger.info(LOG_WARNING.format("DATABASE STRICT THRESHOLD MATCHING COMPLETED. No matches found passing all criteria."))
        else:
            logger.info(LOG_SUCCESS.format(f"DATABASE STRICT THRESHOLD MATCHING COMPLETED. Found {len(final_results)} match(es) after prioritization."))
            for i, match_item in enumerate(final_results): # Renamed 'match' to 'match_item'
                logger.info(LOG_INFO.format(f"  Match #{i+1}: Claim #{match_item['claim_num']}, Score: {match_item['match_score']}, IsSecondary: {match_item['is_secondary']}, HasPendingSec: {match_item['has_pending_secondary']}"))
        
        logger.info(LOG_SECTION_END.format("DB STRICT THRESHOLD MATCHING COMPLETED"))
        logger.info("") # Newline
        
        return final_results

    def find_matching_claims(self, criteria: SearchCriteria, skip_api_fallback: bool = False) -> list[ClaimMatch]:
        """
        Finds claims matching search criteria by scoring candidates from API.
        1. Collects candidates via patient-based search.
        2. Collects candidates via subscriber-based search.
        3. Scores all unique candidates using strict thresholds in _score_api_claim_candidate.
        4. Returns best match(es) after primary/secondary prioritization.
        """
        log_prefix = f"[API Matcher: {criteria.patient_first_name} {criteria.patient_last_name}]"
        logger.info(LOG_SECTION_START.format(f"{log_prefix} API CLAIM MATCHING PROCESS STARTED (STRICT THRESHOLDS)"))
        
        logger.info(LOG_INFO.format(f"\n{log_prefix} SEARCH CRITERIA:"))
        logger.info(LOG_INFO.format(f"  Date of Service:  {criteria.date_of_service}"))
        
        # Use full first and last names from criteria for API queries and subsequent matching
        crit_patient_first_name_full = criteria.patient_first_name
        crit_patient_last_name_full = criteria.patient_last_name
        logger.info(LOG_INFO.format(f"  Patient:          {crit_patient_first_name_full} {crit_patient_last_name_full}"))
        
        crit_subscriber_first_name_full = criteria.subscriber_first_name
        crit_subscriber_last_name_full = criteria.subscriber_last_name
        logger.info(LOG_INFO.format(f"  Subscriber:       {crit_subscriber_first_name_full or 'N/A'} {crit_subscriber_last_name_full or 'N/A'}"))

        # Normalize procedure codes in payment info once (if not already done by caller)
        # _score_api_claim_candidate expects criteria.payment_info.procedures[*].proc_code to be normalized.
        # Assuming they are already normalized as per search_matching_claims.py logic.
        logger.info(LOG_INFO.format(f"  Procedure Codes:  {[p.proc_code for p in criteria.payment_info.procedures]}"))
        
        try:
            target_date = datetime.strptime(criteria.date_of_service, '%Y-%m-%d').date()
        except ValueError:
            logger.error(LOG_ERROR.format(f"{log_prefix} ERROR: Invalid Date of Service format in criteria: {criteria.date_of_service}. Aborting API matching."))
            logger.info(LOG_SECTION_END.format(f"{log_prefix} API CLAIM MATCHING PROCESS COMPLETED (STRICT THRESHOLDS)"))
            return []

        # MIN_ACCEPTABLE_SCORE: _score_api_claim_candidate now returns 0 if any check fails.
        # A successful match will have a score of at least 30(date)+10(status)+20(name_min)+30(proc) = 90.
        # Setting this to 89 to catch anything that passed all internal checks in _score_api_claim_candidate.
        MIN_ACCEPTABLE_SCORE = 89 
        
        all_scored_candidates: List[Dict] = []
        processed_claim_nums = set() # To avoid processing the same claim# multiple times

        # STAGE 1: PATIENT-BASED CANDIDATE COLLECTION
        logger.info(LOG_INFO.format(f"\n{log_prefix} STAGE 1: PATIENT-BASED SEARCH (using full names: '{crit_patient_first_name_full}', '{crit_patient_last_name_full}')"))
        patient_data = None
        # Only proceed if patient names are substantially present in criteria
        if crit_patient_first_name_full and crit_patient_first_name_full.strip() and \
           crit_patient_last_name_full and crit_patient_last_name_full.strip():
            patient_data = self._get_entity_data(
                crit_patient_last_name_full, 
                crit_patient_first_name_full, # Use full first name
                entity_type="patient"
            )
        else:
            logger.info(LOG_INFO.format(f"{log_prefix}   Skipping patient-based API search: Patient first or last name missing/empty in criteria."))
        
        if patient_data and patient_data.get('patient') and patient_data.get('claims'):
            logger.info(LOG_INFO.format(f"{log_prefix}   ✓ Patient Found: ID={patient_data['patient'].get('PatNum')}, Name='{patient_data['patient'].get('FName')} {patient_data['patient'].get('LName')}'"))
            logger.info(LOG_INFO.format(f"{log_prefix}   Found {len(patient_data['claims'])} claims for this patient. Evaluating..."))

            patient_details_for_scoring = patient_data['patient']

            for api_claim in patient_data['claims']:
                claim_num = api_claim.get('ClaimNum')
                if not claim_num or claim_num in processed_claim_nums:
                    continue
                
                # Quick pre-filter (already in _score_api_claim_candidate, but good for early exit)
                try:
                    if datetime.strptime(api_claim.get('DateService', ''), '%Y-%m-%d').date() != target_date:
                        continue
                    if api_claim.get('ClaimStatus') not in ['S', 'H']:
                        continue
                except ValueError:
                    continue

                logger.info(LOG_INFO.format(f"{log_prefix}     Evaluating patient claim ClaimNum: {claim_num}"))
                claim_procs_api = self.make_request(f"claimprocs?ClaimNum={claim_num}")
                if not isinstance(claim_procs_api, list): 
                    logger.warning(LOG_WARNING.format(f"{log_prefix}     Warning: Could not fetch procedures for ClaimNum {claim_num}, or bad response. Skipping."))
                    claim_procs_api = [] 

                score, used_alternate_benefit, override_type = self._score_api_claim_candidate(
                    api_claim_data=api_claim,
                    claim_procedures_from_api=claim_procs_api,
                    criteria=criteria,
                    claim_owner_patient_details=patient_details_for_scoring, 
                    log_prefix=f"{log_prefix}     [ScoreCalc Claim#{claim_num}] "
                )

                if score > 0: # _score_api_claim_candidate returns 0 if any check fails
                    logger.info(LOG_INFO.format(f"{log_prefix}     ClaimNum {claim_num} (Patient Source) scored {score}. Adding as candidate."))
                    all_scored_candidates.append({
                        'score': score,
                        'api_claim_raw': api_claim, 
                        'claim_procs_raw': claim_procs_api, 
                        'source_patient_details': patient_details_for_scoring, 
                        'used_alternate_benefit': used_alternate_benefit,
                        'override_type': override_type
                    })
                    processed_claim_nums.add(claim_num)
                # No explicit else for score == 0, as _score_api_claim_candidate now logs the failure reason.
        else:
            logger.info(LOG_INFO.format(f"{log_prefix}   ✗ No patient found or no claims for patient with Name='{crit_patient_first_name_full} {crit_patient_last_name_full}'."))
            
        # STAGE 2: SUBSCRIBER-BASED CANDIDATE COLLECTION
        logger.info(LOG_INFO.format(f"\n{log_prefix} STAGE 2: SUBSCRIBER-BASED SEARCH (using full names: '{crit_subscriber_first_name_full}', '{crit_subscriber_last_name_full}')"))
        subscriber_data = None
        # Only proceed if subscriber names are substantially present in criteria
        if crit_subscriber_first_name_full and crit_subscriber_first_name_full.strip() and \
           crit_subscriber_last_name_full and crit_subscriber_last_name_full.strip():
            subscriber_data = self._get_entity_data(
                crit_subscriber_last_name_full,
                crit_subscriber_first_name_full, # Use full first name
                entity_type="subscriber"
            )
        else:
            logger.info(LOG_INFO.format(f"{log_prefix}   Skipping subscriber-based API search: Subscriber first or last name missing/empty in criteria."))

        if subscriber_data and subscriber_data.get('subscriber') and subscriber_data.get('inssubs'):
            logger.info(LOG_INFO.format(f"{log_prefix}   ✓ Subscriber Found: ID={subscriber_data['subscriber'].get('PatNum')}, Name='{subscriber_data['subscriber'].get('FName')} {subscriber_data['subscriber'].get('LName')}'"))
            inssub = subscriber_data['inssubs']
            inssub_num = inssub.get('InsSubNum')
            logger.info(LOG_INFO.format(f"{log_prefix}   Insurance SubNum: {inssub_num}. Fetching claims by this InsSubNum."))

            claims_for_sub = self.make_request(f"claims?InsSubNum={inssub_num}")

            if isinstance(claims_for_sub, list) and claims_for_sub:
                logger.info(LOG_INFO.format(f"{log_prefix}   Found {len(claims_for_sub)} claims for InsSubNum {inssub_num}. Evaluating..."))
                for api_claim in claims_for_sub:
                    claim_num = api_claim.get('ClaimNum')
                    if not claim_num or claim_num in processed_claim_nums:
                        continue 

                    try:
                        if datetime.strptime(api_claim.get('DateService', ''), '%Y-%m-%d').date() != target_date:
                            continue
                        if api_claim.get('ClaimStatus') not in ['S', 'H']:
                            continue
                    except ValueError:
                        continue
                    
                    logger.info(LOG_INFO.format(f"{log_prefix}     Evaluating subscriber claim ClaimNum: {claim_num}"))
                    
                    claim_pat_num = api_claim.get('PatNum')
                    if not claim_pat_num:
                        logger.warning(LOG_WARNING.format(f"{log_prefix}     Warning: ClaimNum {claim_num} from subscriber search has no PatNum. Skipping."))
                        continue
                    
                    logger.info(LOG_INFO.format(f"{log_prefix}       Fetching patient details for PatNum {claim_pat_num} (associated with subscriber claim {claim_num})"))
                    owner_patient_api_response = self.make_request(f"patients/{claim_pat_num}")

                    if not owner_patient_api_response or not isinstance(owner_patient_api_response, dict) or not owner_patient_api_response.get("PatNum"):
                        logger.warning(LOG_WARNING.format(f"{log_prefix}       Warning: Could not fetch patient details for PatNum {claim_pat_num} of ClaimNum {claim_num}. Skipping."))
                        continue
                    
                    claim_owner_patient_details_for_scoring = owner_patient_api_response 

                    claim_procs_api = self.make_request(f"claimprocs?ClaimNum={claim_num}")
                    if not isinstance(claim_procs_api, list):
                        logger.warning(LOG_WARNING.format(f"{log_prefix}     Warning: Could not fetch procedures for ClaimNum {claim_num} (Subscriber Source), or bad response. Skipping."))
                        claim_procs_api = []

                    score, used_alternate_benefit, override_type = self._score_api_claim_candidate(
                        api_claim_data=api_claim,
                        claim_procedures_from_api=claim_procs_api,
                        criteria=criteria,
                        claim_owner_patient_details=claim_owner_patient_details_for_scoring,
                        log_prefix=f"{log_prefix}     [ScoreCalc Claim#{claim_num}] "
                    )

                    if score > 0: # _score_api_claim_candidate returns 0 if any check fails
                        logger.info(LOG_INFO.format(f"{log_prefix}     ClaimNum {claim_num} (Subscriber Source) scored {score}. Adding as candidate."))
                        all_scored_candidates.append({
                            'score': score,
                            'api_claim_raw': api_claim,
                            'claim_procs_raw': claim_procs_api,
                            'source_patient_details': claim_owner_patient_details_for_scoring, 
                            'used_alternate_benefit': used_alternate_benefit,
                            'override_type': override_type
                        })
                        processed_claim_nums.add(claim_num)
            else:
                logger.info(LOG_INFO.format(f"{log_prefix}   No claims found for InsSubNum {inssub_num}."))
        else:
            logger.info(LOG_INFO.format(f"{log_prefix}   ✗ No subscriber found or no InsSubs for Subscriber='{crit_subscriber_first_name_full} {crit_subscriber_last_name_full}'."))
        
        # STAGE 3: PROCESS AND PRIORITIZE CANDIDATES
        logger.info(LOG_INFO.format(f"\n{log_prefix} STAGE 3: PROCESSING {len(all_scored_candidates)} CANDIDATES that passed individual checks in _score_api_claim_candidate"))
        
        # Filter by MIN_ACCEPTABLE_SCORE before sorting. 
        # This ensures only high-confidence candidates proceed.
        # Note: _score_api_claim_candidate already returns 0 if any individual check fails,
        # so score > 0 implies individual checks passed. MIN_ACCEPTABLE_SCORE is a safeguard.
        high_confidence_candidates = [cand for cand in all_scored_candidates if cand['score'] >= MIN_ACCEPTABLE_SCORE]
        logger.info(LOG_INFO.format(f"{log_prefix} Found {len(high_confidence_candidates)} candidates with score >= {MIN_ACCEPTABLE_SCORE}"))

        if not high_confidence_candidates:
            logger.warning(LOG_WARNING.format(f"{log_prefix} No suitable API candidates found after all stages and final score threshold."))
            logger.info(LOG_SECTION_END.format(f"{log_prefix} API CLAIM MATCHING PROCESS COMPLETED (STRICT THRESHOLDS)"))
            return []

        # Sort by score descending
        sorted_candidates = sorted(high_confidence_candidates, key=lambda x: x['score'], reverse=True)
        
        final_match_objects_primary: List[ClaimMatch] = []
        final_match_objects_secondary: List[ClaimMatch] = []

        logger.info(LOG_INFO.format(f"{log_prefix} Top {len(sorted_candidates)} high-confidence candidates by score:"))
        for cand_dict in sorted_candidates:
            raw_claim = cand_dict['api_claim_raw']
            raw_procs = cand_dict['claim_procs_raw']
            score = cand_dict['score']
            source_pat_details = cand_dict['source_patient_details']
            used_alternate_benefit = cand_dict.get('used_alternate_benefit', False)
            override_type = cand_dict.get('override_type', '')
            
            logger.info(LOG_INFO.format(f"{log_prefix}   - ClaimNum: {raw_claim['ClaimNum']}, Score: {score}, Date: {raw_claim['DateService']}, Status: {raw_claim['ClaimStatus']}"))
            logger.info(LOG_INFO.format(f"{log_prefix}     Patient on Claim: {source_pat_details.get('FName')} {source_pat_details.get('LName')} (PatNum: {raw_claim['PatNum']})"))

            is_secondary_claim = raw_claim.get('ClaimType') == 'S'
            has_secondary_plan_flag = self._check_secondary_insurance(raw_claim)

            is_ortho_api = raw_claim.get('IsOrtho')
            is_ortho_bool_api = False
            if isinstance(is_ortho_api, str):
                is_ortho_bool_api = is_ortho_api.lower() == 'true'
            elif isinstance(is_ortho_api, bool):
                is_ortho_bool_api = is_ortho_api
            
            ortho_details_api_data = {}
            if is_ortho_bool_api:
                ortho_details_api_data = {
                    "ortho_remain_m": raw_claim.get('OrthoRemainM', 0),
                    "ortho_date": raw_claim.get('OrthoDate', '0001-01-01'),
                    "ortho_total_m": raw_claim.get('OrthoTotalM', 0)
                }

            claim_procs_for_match_obj = []
            for proc_raw in raw_procs:
                claim_proc_num_val = proc_raw.get('ClaimProcNum')
                try:
                    claim_proc_num_int = int(claim_proc_num_val) if claim_proc_num_val is not None else 0
                except (ValueError, TypeError):
                    claim_proc_num_int = 0
                
                claim_procs_for_match_obj.append({
                    "CodeSent": self.normalize_procedure_code(proc_raw.get('CodeSent')), 
                    "FeeBilled": float(proc_raw.get('FeeBilled') or 0),
                    "ClaimProcNum": claim_proc_num_int,
                    "WriteOff": float(proc_raw.get('WriteOff') or 0), 
                    "InsPayAmt": float(proc_raw.get('InsPayAmt') or 0),
                    "DedApplied": float(proc_raw.get('DedApplied') or 0),
                    "Status": proc_raw.get('Status'),
                    "DateInsFinalized": proc_raw.get('DateInsFinalized', proc_raw.get('DateSuppReceived', '')),
                    # Add new UCR fields from API calls
                    "matchesUCR": proc_raw.get('matchesUCR', False),
                    "ucr_amount": float(proc_raw.get('ucr_amount') or 0)
                })

            # Determine match source based on whether alternate benefit logic was used
            match_source = 'api_strict_scored'
            if used_alternate_benefit:
                if override_type == 'count_match':
                    match_source = 'api_count_match'
                elif override_type == 'fee_match':
                    match_source = 'api_alternate_benefit'
                else:
                    match_source = 'api_alternate_benefit'

            match_obj = ClaimMatch(
                claim_num=raw_claim['ClaimNum'],
                pat_num=raw_claim['PatNum'],
                claim_fee=float(raw_claim.get('ClaimFee') or 0),
                date_of_service=raw_claim['DateService'],
                date_sent=raw_claim.get('DateSent'),  # Added DateSent field
                date_received=raw_claim.get('DateReceived'),  # Added DateReceived field
                claim_note=raw_claim.get('ClaimNote', ''),
                is_secondary=is_secondary_claim,
                has_secondary_plan=has_secondary_plan_flag,
                has_pending_secondary=False, 
                match_score=score, 
                match_source=match_source, # Use determined source
                claim_procs=claim_procs_for_match_obj,
                isOrtho=is_ortho_bool_api,
                ortho_details=ortho_details_api_data,
                is_supplemental=False, 
                carrier_name=raw_claim.get('carrier_name', None), # Added to pass carrier name from matched claims
                claim_status=raw_claim.get('claim_status', raw_claim.get('ClaimStatus')) # Added to track claim status
            )

            if is_secondary_claim :
                final_match_objects_secondary.append(match_obj)
            else: 
                 final_match_objects_primary.append(match_obj)

        final_results: List[ClaimMatch] = []
        if final_match_objects_primary:
            logger.info(LOG_INFO.format(f"{log_prefix} Found {len(final_match_objects_primary)} primary API match(es) (strict)."))
            if final_match_objects_secondary:
                logger.info(LOG_INFO.format(f"{log_prefix} Also found {len(final_match_objects_secondary)} secondary API match(es) (strict). Flagging primaries with 'has_pending_secondary'."))
                for p_match in final_match_objects_primary:
                    p_match['has_pending_secondary'] = True
                # Return both primary and secondary claims when both are found
                final_results = final_match_objects_primary + final_match_objects_secondary
                logger.info(LOG_INFO.format(f"{log_prefix} Returning both primary and secondary claims ({len(final_results)} total)."))
            else:
                final_results = final_match_objects_primary
        elif final_match_objects_secondary:
            logger.info(LOG_INFO.format(f"{log_prefix} No primary API matches (strict) found. Found {len(final_match_objects_secondary)} secondary API match(es) (strict)."))
            final_results = final_match_objects_secondary
        
        if final_results:
            logger.info(LOG_SUCCESS.format(f"{log_prefix} Returning {len(final_results)} API match(es) (Strict Scored, Primary preferred):"))
            for i, claim_obj in enumerate(final_results):
                 logger.info(LOG_INFO.format(f"{log_prefix}   Match #{i+1}: Claim #{claim_obj['claim_num']}, Score: {claim_obj['match_score']}, IsSecondary: {claim_obj['is_secondary']}, HasPendingSec: {claim_obj['has_pending_secondary']}"))
        else:
            logger.warning(LOG_WARNING.format(f"{log_prefix} No API candidates met all strict criteria after scoring and prioritization."))
                
        logger.info(LOG_SECTION_END.format(f"{log_prefix} API CLAIM MATCHING PROCESS COMPLETED (STRICT THRESHOLDS)"))
        return final_results

    def find_matching_claims_api_fallback(self, criteria: SearchCriteria, skip_api_fallback: bool = False) -> list[ClaimMatch]:
        """
        API Fallback: Finds "Received" or "Sent" claims for the patient and checks for supplemental matches.
        This is called if no suitable match is found in the cached claims or primary API search.
        If skip_api_fallback is True, this method will return an empty list without performing API calls.
        """
        log_prefix = f"[API Fallback Search: {criteria.patient_first_name} {criteria.patient_last_name}]"
        
        if skip_api_fallback:
            # This print should ideally be a logger.info or logger.warning
            logger.info(LOG_INFO.format(f"{log_prefix} skip_api_fallback is True. Skipping API fallback search for supplemental claims."))
            return []

        # This print should ideally be a logger.info
        logger.info(LOG_INFO.format(f"{log_prefix} INITIATING API FALLBACK SEARCH FOR 'RECEIVED' OR 'SENT' (SUPPLEMENTAL) CLAIMS..."))

        supplemental_matches: List[ClaimMatch] = []
        
        try:
            # For the API fallback, we generally use the patient information from the criteria.
            # First name: take the first part (e.g., "John" from "John Paul")
            api_fallback_patient_first_name = criteria.patient_first_name.split()[0] if criteria.patient_first_name else ""
            
            # Last name: use the full last name from criteria directly.
            # _get_entity_data is now responsible for trying variations if the full LN doesn't match.
            api_fallback_patient_last_name = criteria.patient_last_name

            if not api_fallback_patient_first_name or not api_fallback_patient_last_name:
                logger.warning(LOG_WARNING.format(f"{log_prefix} Insufficient patient name information (FName: '{api_fallback_patient_first_name}', LName: '{api_fallback_patient_last_name}') for API fallback. Aborting."))
                return []

            logger.info(LOG_INFO.format(f"{log_prefix} Calling _get_entity_data with FName='{api_fallback_patient_first_name}', LName='{api_fallback_patient_last_name}'"))
            patient_api_data = self._get_entity_data(
                api_fallback_patient_last_name, # Full last name from criteria
                api_fallback_patient_first_name, 
                entity_type="patient"
            )

            if not patient_api_data or not patient_api_data.get('patient') or not patient_api_data.get('claims'):
                logger.warning(LOG_WARNING.format(f"{log_prefix} Patient not found or no claims found via API for FName='{api_fallback_patient_first_name}', LName='{api_fallback_patient_last_name}'. Cannot search for supplemental."))
                return []

            all_api_claims_for_patient = patient_api_data['claims']
            pat_num = patient_api_data['patient'].get('PatNum')
            
            logger.info(LOG_INFO.format(f"{log_prefix} Found {len(all_api_claims_for_patient)} total API claims for PatNum {pat_num}. Filtering for 'Received' or 'Sent' status."))

            # 2. Filter for "Received" or "Sent" claims
            received_or_sent_api_claims = [c for c in all_api_claims_for_patient if c.get('ClaimStatus') in ['R', 'S']]

            if not received_or_sent_api_claims:
                logger.info(LOG_INFO.format(f"{log_prefix} No 'Received' (ClaimStatus='R') or 'Sent' (ClaimStatus='S') claims found for this patient via API."))
                return []
            
            logger.info(LOG_INFO.format(f"{log_prefix} Found {len(received_or_sent_api_claims)} 'Received' or 'Sent' claims. Checking for date and procedure matches..."))

            target_date_obj = datetime.strptime(criteria.date_of_service, '%Y-%m-%d').date()
            eob_proc_codes_normalized = {
                self.normalize_procedure_code(p.proc_code) for p in criteria.payment_info.procedures if p.proc_code
            }

            for api_claim in received_or_sent_api_claims:
                try:
                    api_claim_date_obj = datetime.strptime(api_claim.get('DateService', ''), '%Y-%m-%d').date()
                    if api_claim_date_obj != target_date_obj:
                        continue # Date mismatch
                except ValueError:
                    logger.warning(LOG_WARNING.format(f"{log_prefix} Invalid DateService format for API claim {api_claim.get('ClaimNum')}. Skipping."))
                    continue

                claim_status_label = 'Received' if api_claim.get('ClaimStatus') == 'R' else 'Sent'
                logger.info(LOG_INFO.format(f"{log_prefix} '{claim_status_label}' API Claim {api_claim.get('ClaimNum')} matches EOB date ({target_date_obj}). Fetching its procedures."))
                
                api_claim_procs_full = self.make_request(f"claimprocs?ClaimNum={api_claim['ClaimNum']}")
                if not api_claim_procs_full:
                    logger.info(LOG_INFO.format(f"{log_prefix} No procedures found for API claim {api_claim.get('ClaimNum')}. Skipping."))
                    continue

                matched_api_procedures_for_claimmatch = []
                for api_proc in api_claim_procs_full:
                    normalized_api_proc_code = self.normalize_procedure_code(api_proc.get('CodeSent'))
                    if normalized_api_proc_code and normalized_api_proc_code in eob_proc_codes_normalized:
                        claim_proc_num_val = api_proc.get('ClaimProcNum')
                        try:
                            claim_proc_num_int = int(claim_proc_num_val) if claim_proc_num_val is not None else 0
                        except (ValueError, TypeError):
                            claim_proc_num_int = 0
                        
                        matched_api_procedures_for_claimmatch.append({
                            "CodeSent": api_proc.get('CodeSent'), 
                            "FeeBilled": float(api_proc.get('FeeBilled') or 0),
                            "ClaimProcNum": claim_proc_num_int,
                            "WriteOff": float(api_proc.get('WriteOff') or 0), 
                            "InsPayAmt": float(api_proc.get('InsPayAmt') or 0),
                            "DedApplied": float(api_proc.get('DedApplied') or 0),
                            "Status": api_proc.get('Status'),
                            "DateInsFinalized": api_proc.get('DateInsFinalized', api_proc.get('DateSuppReceived', '')),
                            # Add new UCR fields from API calls
                            "matchesUCR": api_proc.get('matchesUCR', False),
                            "ucr_amount": float(api_proc.get('ucr_amount') or 0)
                        })
                
                if matched_api_procedures_for_claimmatch:
                    logger.info(LOG_SUCCESS.format(f"{log_prefix} Found {len(matched_api_procedures_for_claimmatch)} overlapping procedures for API Claim {api_claim.get('ClaimNum')}. Creating supplemental match."))
                    
                    is_ortho_api = api_claim.get('IsOrtho')
                    is_ortho_bool_api = False
                    if isinstance(is_ortho_api, str):
                        is_ortho_bool_api = is_ortho_api.lower() == 'true'
                    elif isinstance(is_ortho_api, bool):
                        is_ortho_bool_api = is_ortho_api
                        
                    ortho_details_api_data = {}
                    if is_ortho_bool_api:
                        ortho_details_api_data = {
                            "ortho_remain_m": api_claim.get('OrthoRemainM', 0),
                            "ortho_date": api_claim.get('OrthoDate', '0001-01-01'),
                            "ortho_total_m": api_claim.get('OrthoTotalM', 0)
                        }

                    # Get carrier name for this claim
                    carrier_name = None
                    if hasattr(self, 'make_request') and callable(self.make_request):
                        try:
                            # The make_request is passed from OpenDentalAPI instance
                            from backend.services.integrations.opendental.claims_od_connector.claimsOpenDental import OpenDentalAPI
                            
                            # We need to get the OpenDentalAPI instance that owns this ClaimMatcher
                            if hasattr(self.make_request, '__self__'):
                                api_instance = self.make_request.__self__
                                carrier_name = api_instance.get_carrier_name_from_claim(api_claim)
                                if carrier_name:
                                    logger.info(LOG_INFO.format(f"{log_prefix} Got carrier name for supplemental claim {api_claim['ClaimNum']}: {carrier_name}"))
                        except Exception as e:
                            logger.warning(LOG_WARNING.format(f"{log_prefix} Could not get carrier name for supplemental claim {api_claim['ClaimNum']}: {e}"))

                    match_obj = ClaimMatch(
                        claim_num=api_claim['ClaimNum'],
                        pat_num=pat_num,
                        claim_fee=api_claim.get('ClaimFee', 0),
                        date_of_service=api_claim['DateService'],
                        date_sent=api_claim.get('DateSent'),  # Added DateSent field
                        date_received=api_claim.get('DateReceived'),  # Added DateReceived field
                        claim_note=api_claim.get('ClaimNote', ''),
                        is_secondary=(api_claim.get('ClaimType') == 'S'), 
                        has_secondary_plan=(int(api_claim.get('InsSubNum2', 0)) > 0 or int(api_claim.get('PlanNum2', 0)) > 0), 
                        has_pending_secondary=False, 
                        match_score=None, 
                        match_source='api_supplemental',
                        claim_procs=matched_api_procedures_for_claimmatch,
                        isOrtho=is_ortho_bool_api,
                        ortho_details=ortho_details_api_data,
                        is_supplemental=True,
                        carrier_name=carrier_name,  # Use the fetched carrier name
                        claim_status=api_claim.get('ClaimStatus')  # Added to track claim status
                    )
                    supplemental_matches.append(match_obj)
            
            if supplemental_matches:
                logger.info(LOG_SUCCESS.format(f"{log_prefix} API FALLBACK COMPLETED. Found {len(supplemental_matches)} supplemental match(es)."))
            else:
                logger.info(LOG_INFO.format(f"{log_prefix} API FALLBACK COMPLETED. No supplemental matches found."))
            
            return supplemental_matches

        except Exception as e:
            logger.error(LOG_ERROR.format(f"{log_prefix} ERROR during API fallback supplemental search: {str(e)}"))
            import traceback
            logger.error(traceback.format_exc()) # For detailed debugging
            return [] # Return empty list on error

    def _has_strong_non_procedure_match_with_fees(
        self, 
        claim_date_obj: date, 
        target_date_obj: date, 
        name_score: int, 
        claim_procedures: List[Dict],  # PMS procedures with fee_billed
        eob_procedures: List[ProcedurePayment],  # EOB procedures with submitted_amt
        log_prefix: str = ""
    ) -> bool:
        """
        Enhanced alternate benefit matching that compares individual procedure fees.
        
        This is much stronger evidence than just total amounts because:
        1. It shows the exact same procedures were submitted
        2. Individual fee amounts should match exactly (submitted_amt = fee_billed)
        3. Only the procedure codes differ due to insurance alternate benefits
        
        Strong match criteria:
        - Exact date match
        - High name confidence (score >= 25/30)
        - Individual procedure fees match between PMS and EOB (80%+ of fees)
        """
        
        # Basic criteria (unchanged)
        if claim_date_obj != target_date_obj:
            logger.info(LOG_INFO.format(f"{log_prefix} Date mismatch: {claim_date_obj} vs {target_date_obj}"))
            return False
            
        if name_score < 25:  # Require very high name confidence
            logger.info(LOG_INFO.format(f"{log_prefix} Name score too low: {name_score}/30 < 25"))
            return False
        
        # Enhanced: Individual procedure fee matching
        if not claim_procedures or not eob_procedures:
            logger.info(LOG_INFO.format(f"{log_prefix} Missing procedure data for fee comparison"))
            return False
        
        # Extract fee amounts from both sources
        pms_fees = []
        for proc in claim_procedures:
            fee_billed = proc.get('fee_billed') or proc.get('FeeBilled') or 0
            if fee_billed and float(fee_billed) > 0:
                pms_fees.append(float(fee_billed))
        
        eob_fees = []
        for proc in eob_procedures:
            if hasattr(proc, 'submitted_amt') and proc.submitted_amt > 0:
                eob_fees.append(float(proc.submitted_amt))
        
        if not pms_fees or not eob_fees:
            logger.info(LOG_INFO.format(f"{log_prefix} No valid fees found for comparison (PMS: {len(pms_fees)}, EOB: {len(eob_fees)})"))
            return False
        
        # Sort both lists for comparison
        pms_fees_sorted = sorted(pms_fees)
        eob_fees_sorted = sorted(eob_fees)
        
        logger.info(LOG_INFO.format(f"{log_prefix} PMS fees (sorted): {pms_fees_sorted}"))
        logger.info(LOG_INFO.format(f"{log_prefix} EOB fees (sorted): {eob_fees_sorted}"))
        
        # Check if fee arrays match exactly or very closely
        if len(pms_fees_sorted) != len(eob_fees_sorted):
            logger.info(LOG_INFO.format(f"{log_prefix} Different number of procedures: PMS={len(pms_fees_sorted)}, EOB={len(eob_fees_sorted)}"))
            return False
        
        # Compare each fee pair
        fee_matches = 0
        total_fees = len(pms_fees_sorted)
        
        for i, (pms_fee, eob_fee) in enumerate(zip(pms_fees_sorted, eob_fees_sorted)):
            # Allow small variance for rounding differences
            fee_diff = abs(pms_fee - eob_fee)
            fee_ratio = fee_diff / max(pms_fee, eob_fee) if max(pms_fee, eob_fee) > 0 else 0
            
            if fee_diff <= 1.0 or fee_ratio <= 0.02:  # Exact match or within $1 / 2%
                fee_matches += 1
                logger.info(LOG_INFO.format(f"{log_prefix}   Fee {i+1}: MATCH ${pms_fee} ≈ ${eob_fee}"))
            else:
                logger.info(LOG_INFO.format(f"{log_prefix}   Fee {i+1}: MISMATCH ${pms_fee} vs ${eob_fee} (diff: ${fee_diff:.2f})"))
        
        # Require at least 80% of fees to match for alternate benefit scenario
        fee_match_percentage = fee_matches / total_fees
        
        if fee_match_percentage >= 0.8:
            logger.info(LOG_SUCCESS.format(f"{log_prefix} STRONG ALTERNATE BENEFIT MATCH: {fee_matches}/{total_fees} fees match ({fee_match_percentage*100:.1f}%)"))
            logger.info(LOG_INFO.format(f"{log_prefix}   → Same procedures, same fees, different codes = Alternate Benefit"))
            return True
        else:
            logger.info(LOG_INFO.format(f"{log_prefix} Insufficient fee match: {fee_matches}/{total_fees} ({fee_match_percentage*100:.1f}%) < 80%"))
            return False

    def _has_procedure_count_match(
        self,
        claim_date_obj: date,
        target_date_obj: date,
        name_score: int,
        claim_procedures: List[Dict],  # PMS procedures
        eob_procedures: List[ProcedurePayment],  # EOB procedures
        log_prefix: str = ""
    ) -> bool:
        """
        Fallback procedure matching based on procedure count when codes don't match.
        
        This is a weaker match than code matching but can catch cases where:
        1. Same number of procedures were performed
        2. Strong date and name match exists
        3. Procedure codes differ due to coding variations or alternate benefits
        
        Match criteria:
        - Exact date match
        - High name confidence (score >= 20/30)
        - Same number of procedures
        """
        
        # Basic criteria
        if claim_date_obj != target_date_obj:
            logger.info(LOG_INFO.format(f"{log_prefix} Date mismatch: {claim_date_obj} vs {target_date_obj}"))
            return False
            
        if name_score < 20:  # Require good name confidence (same as main procedure threshold)
            logger.info(LOG_INFO.format(f"{log_prefix} Name score too low for count match: {name_score}/30 < 20"))
            return False
        
        # Count procedures
        claim_proc_count = len(claim_procedures) if claim_procedures else 0
        eob_proc_count = len(eob_procedures) if eob_procedures else 0
        
        if claim_proc_count == 0 and eob_proc_count == 0:
            logger.info(LOG_INFO.format(f"{log_prefix} Both have 0 procedures - count match"))
            return True
        
        if claim_proc_count == eob_proc_count and claim_proc_count > 0:
            logger.info(LOG_SUCCESS.format(f"{log_prefix} PROCEDURE COUNT MATCH: Both have {claim_proc_count} procedures"))
            logger.info(LOG_INFO.format(f"{log_prefix}   → Same count, strong date/name match = Likely same visit"))
            return True
        else:
            logger.info(LOG_INFO.format(f"{log_prefix} Procedure count mismatch: PMS={claim_proc_count}, EOB={eob_proc_count}"))
            return False

    def _has_strong_non_procedure_match(
        self, 
        claim_date_obj: date, 
        target_date_obj: date, 
        name_score: int, 
        claim_fee: float, 
        payment_total: float,
        log_prefix: str = ""
    ) -> bool:
        """
        DEPRECATED: Use _has_strong_non_procedure_match_with_fees for stronger validation.
        
        Determines if a claim has strong enough non-procedure matches to override
        procedure code mismatches (e.g., for alternate benefit scenarios).
        
        Strong match criteria:
        - Exact date match
        - High name confidence (score >= 25/30)
        - Fee amounts within reasonable range (±20%)
        """
        if claim_date_obj != target_date_obj:
            return False
            
        if name_score < 25:  # Require very high name confidence
            return False
            
        # Check if fee amounts are reasonably close (alternate benefits might adjust amounts)
        if payment_total > 0 and claim_fee > 0:
            fee_ratio = min(payment_total, claim_fee) / max(payment_total, claim_fee)
            if fee_ratio < 0.8:  # Amounts should be within 20% of each other
                logger.info(LOG_INFO.format(f"{log_prefix} Fee variance too high for alternate benefit match: Payment ${payment_total:.2f} vs Claim ${claim_fee:.2f} (ratio: {fee_ratio:.2f})"))
                return False
        
        logger.info(LOG_INFO.format(f"{log_prefix} Strong non-procedure match detected: Date exact, Name score {name_score}/30, Fee ratio acceptable"))
        return True

    @staticmethod
    def normalize_name_for_matching(name: str) -> str:
        """
        Comprehensive name normalization to handle common OCR errors, 
        data entry variations, and system artifacts.
        """
        if not name or not name.strip():
            return ""
        
        # Start with basic cleanup
        normalized = name.strip().lower()
        
        # Remove common prefixes/suffixes that might interfere
        prefixes_to_remove = ['dr.', 'dr', 'mr.', 'mr', 'mrs.', 'mrs', 'ms.', 'ms', 'miss']
        suffixes_to_remove = ['jr.', 'jr', 'sr.', 'sr', 'ii', 'iii', 'iv']
        
        # Split into parts for processing
        parts = re.split(r'[\s\-\'\.]+', normalized)
        parts = [part for part in parts if part]  # Remove empty
        
        if not parts:
            return ""
        
        # Remove prefix/suffix parts
        cleaned_parts = []
        for part in parts:
            if part not in prefixes_to_remove and part not in suffixes_to_remove:
                cleaned_parts.append(part)
        
        if not cleaned_parts:
            cleaned_parts = parts  # Fallback to original if all parts removed
        
        # Apply OCR/character substitution fixes
        result_parts = []
        for part in cleaned_parts:
            # Common OCR substitutions
            ocr_fixes = {
                # Number/letter confusion
                '0': 'o', '1': 'l', '5': 's', '8': 'b',
                # Character shape confusion  
                'rn': 'm', 'cl': 'd', 'vv': 'w', 'ii': 'n',
                # Common OCR errors
                'ﬁ': 'fi', 'ﬂ': 'fl', 'oe': 'ce', 'ae': 'a',
                # Scanner artifacts
                '.': '', '_': '', '|': 'l', '\\': '', '/': ''
            }
            
            fixed_part = part
            for bad_char, good_char in ocr_fixes.items():
                fixed_part = fixed_part.replace(bad_char, good_char)
            
            # Handle double letters that might be OCR artifacts
            # But be careful not to break legitimate double letters
            if len(fixed_part) > 2:
                # Only fix if it creates a more reasonable length
                dedupe_part = re.sub(r'(.)\1+', r'\1', fixed_part)
                if len(dedupe_part) >= 2:  # Don't reduce to single character
                    fixed_part = dedupe_part
            
            result_parts.append(fixed_part)
        
        return ' '.join(result_parts)

    @staticmethod
    def calculate_enhanced_similarity(name1: str, name2: str) -> dict:
        """
        Calculate multiple similarity metrics for robust name matching.
        Returns dict with various similarity scores and match types.
        """
        if not name1 or not name2:
            return {'similarity': 0.0, 'match_type': 'no_data', 'score': 0}
        
        # Normalize both names
        norm1 = ClaimMatcher.normalize_name_for_matching(name1)
        norm2 = ClaimMatcher.normalize_name_for_matching(name2)
        
        if not norm1 or not norm2:
            return {'similarity': 0.0, 'match_type': 'empty_after_norm', 'score': 0}
        
        # Exact match after normalization
        if norm1 == norm2:
            return {'similarity': 1.0, 'match_type': 'exact_normalized', 'score': 15}
        
        # Substring/truncation analysis
        shorter = norm1 if len(norm1) < len(norm2) else norm2
        longer = norm2 if len(norm1) < len(norm2) else norm1
        
        # High-confidence truncation matches
        if len(shorter) >= 2 and shorter in longer:
            if longer.startswith(shorter):
                return {'similarity': 0.95, 'match_type': 'prefix_truncation', 'score': 12}
            elif longer.endswith(shorter):
                return {'similarity': 0.95, 'match_type': 'suffix_truncation', 'score': 12}
            elif shorter in longer:
                return {'similarity': 0.85, 'match_type': 'substring_truncation', 'score': 10}
        
        # Levenshtein distance calculation
        distance = ClaimMatcher.levenshtein_distance(norm1, norm2)
        max_len = max(len(norm1), len(norm2))
        levenshtein_similarity = 1.0 - (distance / max_len) if max_len > 0 else 0.0
        
        # Character overlap analysis (for very different but related names)
        chars1 = set(norm1)
        chars2 = set(norm2)
        char_overlap = len(chars1 & chars2) / len(chars1 | chars2) if chars1 or chars2 else 0.0
        
        # Phonetic similarity (basic soundex-like approach)
        def simple_soundex(name):
            if not name:
                return ""
            # Keep first letter, remove vowels, dedupe consonants
            result = name[0]
            for char in name[1:]:
                if char not in 'aeiou' and (not result or char != result[-1]):
                    result += char
            return result[:4].ljust(4, '0')
        
        phonetic_match = simple_soundex(norm1) == simple_soundex(norm2)
        
        # Determine best match type and score
        if levenshtein_similarity >= 0.9:
            return {'similarity': levenshtein_similarity, 'match_type': 'high_similarity', 'score': 12}
        elif levenshtein_similarity >= 0.8:
            return {'similarity': levenshtein_similarity, 'match_type': 'good_similarity', 'score': 10}
        elif levenshtein_similarity >= 0.7:
            return {'similarity': levenshtein_similarity, 'match_type': 'fair_similarity', 'score': 8}
        elif levenshtein_similarity >= 0.6:
            return {'similarity': levenshtein_similarity, 'match_type': 'weak_similarity', 'score': 5}
        elif phonetic_match and char_overlap > 0.5:
            return {'similarity': 0.6, 'match_type': 'phonetic_match', 'score': 6}
        elif char_overlap > 0.7:
            return {'similarity': char_overlap, 'match_type': 'character_overlap', 'score': 4}
        else:
            return {'similarity': levenshtein_similarity, 'match_type': 'poor_match', 'score': 0}