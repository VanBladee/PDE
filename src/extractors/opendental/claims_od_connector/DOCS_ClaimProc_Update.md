ClaimProcs PUT (update)
Version Added: 22.3.33

ClaimProcs are complex. They are used to link procedures to claims, insurance payments to procedures or claims, and insurance estimates to procedures without a claim. See Claim Procedures ( claimprocs ) and Claim for more details.

Updates a ClaimProc exactly as in Open Dental, performing the same calculations for necessary fields. All below fields are optional. However, which fields can be changed depends on the status of the ClaimProc and the Claim (if associated). Editing a received ClaimProc can delete all of the Income Transfers on the claim.

Cannot update a ClaimProc that has IsTransfer set to true, or a Status of "Adjustment", "InsHist", "CapClaim", "CapComplete", or "CapEstimate". To update a ClaimProc with a Status of Adjustment, use ClaimProcs PUT InsAdjust.

Updating a ClaimProc recalculates the claim totals of the Claim to which it's attached. BlueBook values are not updated. Override field values use -1 to represent none or blank.

ClaimProcNum: Required in the URL.

ProvNum: ProvNum of a provider. Follows the ProcProvChangesClaimProcWithClaim preference. See Claimproc Provider for more information.
FeeBilled: The amount billed to insurance.
DedApplied: Deductible applied to this procedure only. DedApplied will always match the DedEstOverride value when ClaimProc status is NotReceived or Preauth.
Status: Either "NotReceived", "Received", "Preauth", "Supplemental", or "Estimate". When set to Received or Supplemental, ClaimProc.DateEntry will be updated to DateTime.Now.
InsPayAmt: Amount insurance actually paid. Cannot be updated once the procedure is attached to a check.
Remarks: The remarks that insurance sends in the EOB about procedures. Overwrites any existing Remarks.
ClaimPaymentNum: (Added in version 24.3.24) ClaimPaymentNum of a partial claimpayment. Attaches this ClaimProc, alongside any other able ClaimProcs on the same Claim, to the specified ClaimPayment. Can supply 0 to detach this ClaimProc, and all other ClaimProcs from the same claim that are on the same ClaimPayment. See Finalize Insurance Payment and Batch Insurance Payment for more information.
WriteOff: Amount not covered by insurance which is written off.
CodeSent: The procedure code that was sent to insurance. Usually it is the same as the actual procedure code, but may be different if using alternate codes (for example: Medicaid), medical codes, or custom codes with suffixes that get removed before being sent. See also Incorrect Procedures on Claim. Use ProcedureCodes GET to get a list of valid codes.
PercentOverride: The percentage that insurance is expected to cover. A number between 0 and 100. Use -1 to indicate no override.
NoBillIns: (Added in version 23.2.10) Determines if the procedure should be billed to the insurance plan. Either "true" or "false". Set to true to not bill to the insurance plan and remove all estimate and override field values.
CopayOverride: Based on the insurance plan's copay fee schedule, and subtracted from the amount that insurance will pay. Use -1 to indicate no override.
DedEstOverride: The amount that the patient must pay each year before insurance kicks in, and always subtracted before Percentage is calculated. Use -1 to indicate no override.
InsEstTotalOverride: The estimated amount that insurance will pay. If the claimproc is already attached to a claim, this will not affect the patient balance. Use -1 to indicate no override.
PaidOtherInsOverride: Adds up all amounts paid by insurance plans that are lower in order. Use -1 to indicate no override.
WriteOffEstOverride: WriteOff amount usually only used for PPOs. Use -1 to indicate no override.
ClaimPaymentTracking: Used to document information about the payment of the procedure. Useful to track why payment was rejected. See also Definitions: Claim Payment Tracking. Definition.DefNum where definition.Category=36.

Example Request:
PUT /claimprocs/293

{
"Status": "Received",
"InsPayAmt": "50.00"
}

or

{
"ProvNum": 10,
"FeeBilled": "65.00",
"DedApplied": "5",
"Status": "Received",
"InsPayAmt": "50.00",
"Remarks": "Patient has reached their annual limit",
"WriteOff": "5",
"CodeSent": "D0021",
"PercentOverride": "-1",
"CopayOverride": "-1",
"DedEstOverride": "-1",
"InsEstTotalOverride": "50",
"PaidOtherInsOverride": "-1",
"WriteOffEstOverride": "-1",
"ClaimPaymentTracking": 448
}

Example Response:
{
"ClaimProcNum": 293,
"ProcNum": 966,
"ClaimNum": 45,
"PatNum": 72,
"ProvNum": 10,
"FeeBilled": 65.0,
"InsPayEst": 50.0,
"DedApplied": 5.0,
"Status": "Received",
"InsPayAmt": 50.0,
"Remarks": "Patient has reached their annual limit",
"ClaimPaymentNum": 0,
"PlanNum": 3,
"DateCP": "2022-11-23",
"WriteOff": 5.0,
"CodeSent": "D0021",
"AllowedOverride": -1.0,
"Percentage": 0,
"PercentOverride": -1,
"CopayAmt": -1.0,
"NoBillIns": "false",
"PaidOtherIns": 0.0,
"BaseEst": 0.0,
"CopayOverride": -1.0,
"ProcDate": "2022-12-02",
"DateEntry": "2022-12-02",
"DedEst": 0.0,
"DedEstOverride": -1.0,
"InsEstTotal": 0.0,
"InsEstTotalOverride": 50.0,
"PaidOtherInsOverride": -1.0,
"EstimateNote": "",
"WriteOffEst": -1.0,
"WriteOffEstOverride": -1.0,
"ClinicNum": 3,
"InsSubNum": 13,
"PaymentRow": 0,
"PayPlanNum": 0,
"ClaimPaymentTracking": 448,
"claimPaymentTracking": "Paid In Full",
"SecUserNumEntry": 1,
"SecDateEntry": "2022-11-23",
"SecDateTEdit": "2022-12-02 11:46:14",
"DateSuppReceived": "2022-12-02",
"DateInsFinalized": "0001-01-01",
"IsTransfer": "false",
"ClaimAdjReasonCodes": ""
}

200 OK
400 Bad Request (with explanation)
404 NotFound (with explanation)

ClaimProcs PUT InsAdjust
Version Added: 21.1

This adds or changes a claimproc that is acting as an insurance adjustment. PatPlanNum is required. You can obtain the PatPlanNum from FamilyModules GET Insurance. "date" is optional and defaults to today. It should be a date within the benefit year that you are interested in. Any adjustment that is created will also use that date. Either insUsed or deductibleUsed is Required. Pass in the total insurance and/or deductible used. The logic will take into consideration existing paid claims. For example, if payments of $200 are already entered into Open Dental, and you pass in insUsed of $300, then it will result in a $100 adjustment so that it will properly show the $300. If the insUsed passed in exactly equals payments already in Open Dental, then any existing adjustment will be deleted. The calculations do not distinguish family or lifetime benefits.

PatPlanNum: Required.
insUsed: This or deductibleUsed is required.
deductibleUsed: This or insUsed is required.
date: Optional. String in "yyyy-MM-dd" format. Default today's date.

Example Request:
PUT /claimprocs/InsAdjust

{
"PatPlanNum": 123,
"date": "2020-01-01",
"insUsed":"300",
"deductibleUsed":"25"
}

Example Response:
200 OK (Regardless of how the math worked out. ClaimProcs could have been added or deleted.)

ClaimProcs POST InsAdjust
Version Added: 23.2.5

Creates a claimproc that is acting as an insurance adjustment. See Adjustments to Insurance Benefits for more information.

PatPlanNum: Required.
insUsed: Optional. Default 0.
deductibleUsed: Optional. Default 0.
date: Optional. String in "yyyy-MM-dd" format. Default today's date.

Example Request:
POST /claimprocs/InsAdjust

{
"PatPlanNum": 123,
"date": "2023-07-18",
"insUsed":"300.75",
"deductibleUsed":"25.99"
}

Example Response:
{
"ClaimProcNum": 1117,
"ProcNum": 0,
"ClaimNum": 0,
"PatNum": 72,
"ProvNum": 0,
"FeeBilled": 0.0,
"InsPayEst": 0.0,
"DedApplied": 25.99,
"Status": "Adjustment",
"InsPayAmt": 300.75,
"Remarks": "",
"ClaimPaymentNum": 0,
"PlanNum": 38,
"DateCP": "0001-01-01",
"WriteOff": 0.0,
"CodeSent": "",
"AllowedOverride": 0.0,
"Percentage": 0,
"PercentOverride": 0,
"CopayAmt": 0.0,
"NoBillIns": "false",
"PaidOtherIns": 0.0,
"BaseEst": 0.0,
"CopayOverride": 0.0,
"ProcDate": "2023-07-18",
"DateEntry": "0001-01-01",
"DedEst": 0.0,
"DedEstOverride": 0.0,
"InsEstTotal": 0.0,
"InsEstTotalOverride": 0.0,
"PaidOtherInsOverride": 0.0,
"EstimateNote": "",
"WriteOffEst": 0.0,
"WriteOffEstOverride": 0.0,
"ClinicNum": 0,
"InsSubNum": 30,
"PaymentRow": 0,
"PayPlanNum": 0,
"ClaimPaymentTracking": 0,
"claimPaymentTracking": "",
"SecUserNumEntry": 0,
"SecDateEntry": "2023-08-01",
"SecDateTEdit": "2023-08-01 14:41:25",
"DateSuppReceived": "0001-01-01",
"DateInsFinalized": "0001-01-01",
"IsTransfer": "false",
"ClaimAdjReasonCodes": ""
}

201 Created
400 BadRequest (with explanation)
404 NotFound (with explanation)