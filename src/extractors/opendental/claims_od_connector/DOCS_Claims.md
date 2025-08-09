Claims POST (create)
Version Added: 23.2.5

Creates a new claim. See Claims, Preauthorization, and Insurance Plan for more information. Use Claims PUT to modify additional fields on the claim. Use ClaimProcs PUT to modify the Claim Procedures ( claimprocs ) attached to the claim.

The insurance plan specified must be associated with the patient. Creating a primary or secondary claim will use the patient's primary or secondary insurance respectively.

PatNum: Required. FK to patient.PatNum.
procNums: Required. An array of ProcNums, in [1,2,3] format to attach to this Claim.
ClaimType: Required. Either "P" for primary, "S" for secondary, or "PreAuth" for preauthorization.
InsSubNum: Required only when ClaimType is "PreAuth". FK to inssub.InsSubNum. The insurance plan used for the claim. Default to the patient's primary or secondary insurance on file when creating a primary or secondary claim.
InsSubNum2: Optional. FK to inssub.InsSubNum. The "Other Coverage" insurance for the claim. Default to 0.
PatRelat: Required only when ClaimType is "PreAuth". Either "Self", "Spouse", "Child", "Employee", "HandicapDep", "SignifOther", "InjuredPlaintiff", "LifePartner", or "Dependent". Default to the patient's relationship to the plan's subscriber for primary and secondary claims.
PatRelat2: Optional. Either "Self", "Spouse", "Child", "Employee", "HandicapDep", "SignifOther", "InjuredPlaintiff", "LifePartner", or "Dependent". If using InsSubNum2, will default to the patient's relationship to the plan's subscriber.
DateService: Optional. String in "yyyy-MM-dd" format. Default to same date as earliest procedure from procNums array. Ignored if ClaimType is "PreAuth".
DateSent: Optional. String in "yyyy-MM-dd" format. Default to today.
ClaimForm: Optional. FK to claimform.ClaimFormNum. Default to ClaimForm attached to Insurance Plan.
ProvTreat: Optional. FK to provider.ProvNum. Default to same treating provider when creating a claim in Open Dental.
ProvBill: Optional. FK to provider.ProvNum. Default to same billing provider when creating a claim in Open Dental.

Example Request:
POST /claims

{
"PatNum": 1337,
"procNums": [12857, 12859, 12952],
"ClaimType": "P"
}

or

{
"PatNum": 1337,
"procNums": [12857, 12859, 12952],
"ClaimType": "PreAuth",
"InsSubNum": 894,
"PatRelat": "Employee"
}

or

{
"PatNum": 1337,
"procNums": [12857, 12859, 12952],
"ClaimType": "PreAuth",
"InsSubNum": 894,
"InsSubNum2": 856,
"PatRelat": "Self",
"PatRelat2": "Spouse",
"DateService": "2023-05-19",
"DateSent": "2023-05-21",
"ClaimForm": 19,
"ProvTreat": 8,
"ProvBill": 2
}

Example Response:
{
"ClaimNum": 35879
"PatNum": 1337,
"DateService": "0001-01-01",
"DateSent": "2023-05-21",
"ClaimStatus": "W",
"DateReceived": "0001-01-01",
"PlanNum": 31,
"ProvTreat": 8,
"ClaimFee": 295.5,
"InsPayEst": 220.0,
"InsPayAmt": 0.0,
"DedApplied": 0.0,
"IsProsthesis": "N",
"PriorDate": "0001-01-01",
"ReasonUnderPaid": "",
"ClaimNote": "",
"ClaimType": "PreAuth",
"ProvBill": 2,
"PlaceService": "Office",
"AccidentRelated": "",
"AccidentDate": "0001-01-01",
"AccidentST": "",
"IsOrtho": "False",
"OrthoRemainM": 0,
"OrthoDate": "0001-01-01",
"PatRelat": "Self",
"PlanNum2": 28,
"PatRelat2": "Spouse",
"WriteOff": 0.0,
"ClaimForm": "19",
"InsSubNum": 894,
"InsSubNum2": 856,
"PriorAuthorizationNumber": "",
"CustomTracking": 0,
"customTracking": "",
"OrthoTotalM": 0,
"SecDateTEdit": "2023-05-21 10:25:44"
}

201 Created
400 BadRequest (with explanation)
404 NotFound (with explanation)

Claims PUT (update)
Version Added: 21.4

All fields are optional and it is common to only set one or two fields.

ClaimNum: Required in the URL.

ClaimStatus: Single character. "U" for Unsent, "H" for Hold until pri received, "W" for Waiting in queue, "S" for Sent or "R" for Received.
DateReceived: Date the claim was received. String in "yyyy-MM-dd" format.
ProvTreat: ProvNum of treating provider for dental claims.
IsProsthesis: Single character. "N" for No, "I" for Initial or "R" for Replacement.
PriorDate: Date prior prosthesis was placed. This is only for paper claims. E-claims have a date field on each individual procedure. String in "yyyy-MM-dd" format.
ClaimNote: Note to be sent to insurance. E-Claims have notes on each procedure. Will overwrite existing note.
ReasonUnderPaid: (Added in version 22.3.31) Note on a patient's statement explaining why the insurance does not pay as much as expected. Will overwrite existing note.
ProvBill: ProvNum of billing provider.
PlaceService: Service location. Usually "Office". See Database Schema for other options.
AccidentRelated: Type of accident. "No" for No, "A" for Auto, "E" for Employment, or "O" for Other.
AccidentDate: (Added in version 22.1) Date of accident. String in "yyyy-MM-dd" format.
AccidentST: Accident state. Two characters.
IsOrtho: Either "true" or "false".
OrthoRemainM: (Added in version 23.2.18) Remaining months of ortho. Valid values are 1-36.
OrthoDate: Date the ortho appliance was placed. Cannot change date if "Use the first ortho procedure date as Date of Placement" pref is enabled during Ortho Setup. String in "yyyy-MM-dd" format.
PatRelat: (Added in version 24.4.35) Optional. Either "Self", "Spouse", "Child", "Employee", "HandicapDep", "SignifOther", "InjuredPlaintiff", "LifePartner", or "Dependent". The relationship to the subscriber of the insurance plan on this claim.
PatRelat2: (Added in version 24.4.35) Optional. Either "Self", "Spouse", "Child", "Employee", "HandicapDep", "SignifOther", "InjuredPlaintiff", "LifePartner", or "Dependent". The relationship to the subscriber for "Other Coverage" on this claim.
ClaimForm: FK to claimform.ClaimFormNum. Is 0 if not assigned to use the claimform for the insplan.
InsSubNum2: (Added in version 24.4.35) Optional. FK to inssub.InsSubNum. The "Other Coverage" insurance for the claim.
PriorAuthorizationNumber: (Rare) Also called the preauthorization number. Typically used for medical claims. This is NOT the predetermination of benefits number.
OrthoTotalM: Estimated months of ortho. Valid values are 1-36.

Example Request:
PUT /claims/21

{
"ClaimStatus": "R",
"DateReceived": "2021-05-25",
"ProvTreat": 1,
"IsProsthesis": "N",
"PriorDate": "2020-06-26",
"ClaimNote": "Existing RCT from 2019-05-14.",
"ProvBill": 1,
"PlaceService": "Office",
"AccidentRelated": "O",
"AccidentDate": "2021-05-15",
"AccidentST": "MO",
"IsOrtho": "true",
"OrthoRemainM": 12,
"OrthoDate": "2021-05-25",
"PatRelat2": "Spouse",
"ClaimForm": 0,
"InsSubNum2": 856,
"PriorAuthorizationNumber": "6549848516",
"OrthoTotalM": 36
}

Example Response:
{
"ClaimNum": 21
"PatNum": 1337,
"DateService": "0001-01-01",
"DateSent": "2021-04-13",
"ClaimStatus": "R",
"DateReceived": "2021-05-25",
"PlanNum": 31,
"ProvTreat": 1,
"ClaimFee": 295.5,
"InsPayEst": 220.0,
"InsPayAmt": 0.0,
"DedApplied": 0.0,
"IsProsthesis": "N",
"PriorDate": "2020-06-26",
"ReasonUnderPaid": "",
"ClaimNote": "",
"ClaimType": "PreAuth",
"ProvBill": 2,
"PlaceService": "Office",
"AccidentRelated": "O",
"AccidentDate": "2021-05-15",
"AccidentST": "MO",
"IsOrtho": "True",
"OrthoRemainM": 12,
"OrthoDate": "2021-05-25",
"PatRelat": "Self",
"PlanNum2": 28,
"PatRelat2": "Spouse",
"WriteOff": 0.0,
"ClaimForm": "0",
"InsSubNum": 894,
"InsSubNum2": 856,
"PriorAuthorizationNumber": "6549848516",
"CustomTracking": 0,
"customTracking": "",
"OrthoTotalM": 36,
"SecDateTEdit": "2023-05-21 10:25:44"
}

200 OK
400 BadRequest (with explanation)
404 NotFound (with explanation)

Claims PUT Status
Version Added: 21.3

Rarely used. Probably just use Claims PUT instead.

Sets the ClaimStatus of a claim to "Sent" and automatically creates an Etrans entry.

ClaimNum: Required in the URL.
DateSent: Required. Date the claim was most recently sent. String in "yyyy-MM-dd" format."
DateSentOrig: Optional. String in "yyyy-MM-dd" format. Defaults to DateSent. Will be ignored for claims that have been marked as "Sent" previously.

Example Requests:
PUT /claims/26/Status

{
"DateSent": "2021-09-13"
}

{
"DateSent": "2021-09-13",
"DateSentOrig": "2021-09-01"
}

Example Response:
{
"ClaimNum": 35879
"PatNum": 1337,
"DateService": "0001-01-01",
"DateSent": "2021-09-13",
"ClaimStatus": "W",
"DateReceived": "0001-01-01",
"PlanNum": 31,
"ProvTreat": 8,
"ClaimFee": 295.5,
"InsPayEst": 220.0,
"InsPayAmt": 0.0,
"DedApplied": 0.0,
"IsProsthesis": "N",
"PriorDate": "0001-01-01",
"ReasonUnderPaid": "",
"ClaimNote": "",
"ClaimType": "PreAuth",
"ProvBill": 2,
"PlaceService": "Office",
"AccidentRelated": "",
"AccidentDate": "0001-01-01",
"AccidentST": "",
"IsOrtho": "False",
"OrthoRemainM": 0,
"OrthoDate": "0001-01-01",
"PatRelat": "Self",
"PlanNum2": 28,
"PatRelat2": "Spouse",
"WriteOff": 0.0,
"ClaimForm": "19",
"InsSubNum": 894,
"InsSubNum2": 856,
"PriorAuthorizationNumber": "",
"CustomTracking": 0,
"customTracking": "",
"OrthoTotalM": 0,
"SecDateTEdit": "2023-05-21 10:25:44"
}

200 OK
400 BadRequest (Missing or invalid fields)
404 NotFound "Claim not found"

Claims PUT Split
Version Added: 22.1

Splits an existing claim. Moves the specified procedure(s) sent with the request from the original claim to a newly created one. Use Claims GET and ClaimProcs GET to obtain ClaimNum and ProcNums of desired procedures.

ClaimNum: Required in the URL.
ProcNums: Required. An array of ProcNums, in [1,2,3] format.

Example Requests:
PUT /claims/26/Split

{
"ProcNums": [153, 154, 155]
}

Example Response:

{
"ClaimNum": 27,
"ProcNums": [153, 154, 155]
}

201 Created
400 BadRequest (Missing or invalid fields)
404 NotFound