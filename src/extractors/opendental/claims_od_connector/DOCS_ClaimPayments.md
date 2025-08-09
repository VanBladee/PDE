ClaimPayments POST
Version Added: 22.4.8

Finalize a claimpayment for a single Claim. Cannot use this method if the dental office has the preference ClaimPaymentBatchOnly set to true. Does not link Deposits or Attach EOBs.

Prior to running this method, use ClaimProcs PUT (update) to update the Status to either "Received" or "Supplemental", and finalize the InsPayAmt. ClaimProc.InsPayAmt cannot be updated when there is already a ClaimPayment attached. Then use Claims PUT (update) to update the Claim ClaimStatus to "R" (Received).

claimNum: Required. FK to Claim.ClaimNum that is receiving the payment.
CheckAmt: Required. The amount of the check. Must match the total of the ClaimProcs' InsPayAmt for all of the ClaimProcs attached to the Claim that have a ClaimPaymentNum of 0.

CheckDate: Optional. Date the check was entered into this system, not the date on the check. String in "yyyy-MM-dd" format. Default today's date.
CheckNum: Optional. The check number.
BankBranch: Optional. Bank and branch.
Note: Optional. Note for this check if needed.
ClinicNum: Optional. Default is the ClinicNum of the Claim.
CarrierName: Optional. Default is the CarrierName attached to the InsPlan that is attached to the Claim.
DateIssued: Optional. Date that the carrier issued the check. Date on the check. String in "yyyy-MM-dd" format.
PayType: Optional. Definition.DefNum where category=32. See also Definitions: Insurance Payment Types. Default is the first definition in that Category.
PayGroup: Optional. Definition.DefNum where category=40. See also Definitions: Claim Payment Groups. Default is the first definition in that Category.

Example Requests:
POST /claimpayments

{
"claimNum": 3567,
"CheckAmt": "567.42"
}

or

{
"claimNum": 3567,
"CheckAmt": "567.42",
"CheckDate": "2022-10-25",
"CheckNum": "1234",
"BankBranch": "124-85425",
"Note": "Check was lost in mail, but envelope is dated appropriately.",
"ClinicNum": 3,
"CarrierName": "Great Insurance",
"DateIssued": "2022-10-20",
"PayType": 386,
"PayGroup": 394
}

Example Response:
{
"ClaimPaymentNum": 897,
"CheckDate": "2022-10-25",
"CheckAmt": "567.42",
"CheckNum": "1234",
"BankBranch": "124-85425",
"Note": "Check was lost in mail, but envelope is dated appropriately.",
"ClinicNum": 3,
"DepositNum": 0,
"CarrierName": "Great Insurance",
"DateIssued": "2022-10-20",
"IsPartial": "false",
"PayType": 386,
"payType": "Check",
"SecUserNumEntry": 0,
"SecDateEntry": "2022-10-25",
"SecDateTEdit": "2022-10-11 12:54:48",
"PayGroup": 394,
"payGroup": "Default"
}

201 Created
400 BadRequest (with explaination)
404 NotFound (with explaination)

ClaimPayments POST Batch
Version Added: 24.2.18

Create a batch claimpayment. Creates an Auto Deposit if the dental office has the preference ShowAutoDeposit set to true. Does not attach EOBs. See Batch Insurance Payment.

Prior to running this method, use ClaimProcs PUT (update) to update the Status to either "Received" or "Supplemental", and finalize the InsPayAmt. ClaimProc.InsPayAmt cannot be updated when there is already a ClaimPayment attached. Then use Claims PUT (update) to update the Claim ClaimStatus to "R" (Received).

claimNums: Required. An array of ClaimNums that are receiving the payment, in [1,2,3] format.
CheckAmt: Required. The amount of the check. If the amount differs from the total of the ClaimProcs' InsPayAmt for all of the ClaimProcs attached to the Claim that have a ClaimPaymentNum of 0, then this ClaimPayment will be marked as partial.

CheckDate: Optional. Date the check was entered into this system, not the date on the check. String in "yyyy-MM-dd" format. Default today's date.
CheckNum: Optional. The check number.
BankBranch: Optional. Bank and branch.
Note: Optional. Note for this payment.
ClinicNum: Optional. Default 0.
CarrierName: Optional. Default is the CarrierName attached to the InsPlan that is attached to the first Claim in the claimNums list.
DateIssued: Optional. Date that the carrier issued the payment. String in "yyyy-MM-dd" format. Default "0001-01-01".
PayType: Optional. definition.DefNum where category=32. See also Definitions: Insurance Payment Types. Default is the first definition in that Category.
PayGroup: Optional. definition.DefNum where category=40. See also Definitions: Claim Payment Groups. Default is the first definition in that Category.

Example Requests:
POST /claimpayments/Batch

{
"claimNums": [2547, 2568, 2591],
"CheckAmt": "350.35"
}

or

{
"claimNums": [2547, 2568, 2591],
"CheckAmt": "350.35",
"CheckDate": "2024-05-25",
"CheckNum": "5678",
"BankBranch": "124-85425",
"Note": "Check was lost in mail, but envelope is dated appropriately.",
"ClinicNum": 2,
"CarrierName": "Greater Insurance",
"DateIssued": "2024-05-10",
"PayType": 386,
"PayGroup": 394
}

Example Response:
{
"ClaimPaymentNum": 905,
"CheckDate": "2024-05-25",
"CheckAmt": "350.35",
"CheckNum": "5678",
"BankBranch": "124-85425",
"Note": "Check was lost in mail, but envelope is dated appropriately.",
"ClinicNum": 2,
"DepositNum": 0,
"CarrierName": "Greater Insurance",
"DateIssued": "2024-05-10",
"IsPartial": "true",
"PayType": 386,
"payType": "Check",
"SecUserNumEntry": 0,
"SecDateEntry": "2024-05-25",
"SecDateTEdit": "2024-05-25 10:03:37",
"PayGroup": 394,
"payGroup": "Default"
}

201 Created
400 BadRequest (with explanation)
404 NotFound (with explanation)

ClaimPayments PUT
Version Added: 23.2.15

Updates an existing claimpayment by ClaimPaymentNum. See Finalize Insurance Payment.

ClaimPaymentNum: Required in the URL.

CheckNum: Optional. The check number.
BankBranch: Optional. Bank and branch.
Note: Optional. Note for this check if needed. Replaces existing Note.
CarrierName: Optional. Descriptive name of the carrier just for reporting purposes.
PayType: Optional. Definition.DefNum where definition.Category=32. See also Definitions: Insurance Payment Types.
PayGroup: Optional. Definition.DefNum where definition.Category=40. See also Definitions: Claim Payment Groups.

Example Request:
PUT /claimpayments/1434

{
"CheckNum": "758946",
"BankBranch": "124-85425",
"Note": "Check was lost in mail, but envelope is dated appropriately.",
"CarrierName": "ODS Oregon Dental Service",
"PayType": 356,
"PayGroup": 412
}

Example Response:
{
"ClaimPaymentNum": 1434,
"CheckDate": "2023-08-16",
"CheckAmt": "567.42",
"CheckNum": "758946",
"BankBranch": "124-85425",
"Note": "Check was lost in mail, but envelope is dated appropriately.",
"ClinicNum": 3,
"DepositNum": 0,
"CarrierName": "ODS Oregon Dental Service",
"DateIssued": "2023-08-14",
"IsPartial": "false",
"PayType": 356
"payType": "Check",
"SecUserNumEntry": 0,
"SecDateEntry": "2023-08-16",
"SecDateTEdit": "2023-08-17 12:53:39",
"PayGroup": 412,
"payGroup": "Default"
}

200 OK
400 BadRequest (with explanation)
404 NotFound (with explanation)