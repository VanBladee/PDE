EobAttaches GET
Version Added: 23.3.8

Gets a list of eobattaches by ClaimPaymentNum.

ClaimPaymentNum: Required. FK to claimpayment.ClaimPaymentNum.

Example Request:
GET /eobattaches?ClaimPaymentNum=23

Example Response:
[
{
"EobAttachNum": 10,
"ClaimPaymentNum": 23,
"DateTCreated": "2021-02-16 09:43:17",
"FileName": "20210216_153711_10.png",
"RawBase64": ""
},
{
"EobAttachNum": 15,
"ClaimPaymentNum": 23,
"DateTCreated": "2021-02-18 11:23:10",
"FileName": "20210218_153711_15.png",
"RawBase64": ""
},
{
"EobAttachNum": 21,
"ClaimPaymentNum": 23,
"DateTCreated": "2021-02-20 08:30:11",
"FileName": "20210220_153711_21.png",
"RawBase64": ""
},
etc...
]

200 OK
400 BadRequest (with explanation)
404 NotFound (with explanation)

EobAttaches POST DownloadSftp
Version Added: 23.3.12

This will place an image file on an SFTP site that you specify. After running this method, download the resulting file from your SFTP site. The user with the SFTP credentials must have write permission in this directory. Directory will be created if it does not exist, and files already existing with the specified name will be overwritten. If the SftpAddress does not contain a file name, the eobattach.FileName will be used. All file storage options (LocalAtoZ, InDatabase, and Cloud) are supported.

EobAttachNum: Required.
SftpAddress: Required. Specify the full path of the file (using /). The user with the SFTP credentials must have write permission in this directory.
SftpUsername: Required.
SftpPassword: Required.

Example Request:
POST /eobattaches/DownloadSftp

{
"EobAttachNum": 10,
"SftpAddress": "MySftpSite/myUsername/EOBs/20210220_153711_10.png",
"SftpUsername": "myUsername",
"SftpPassword": "myPassword"
}

Example Response:

201 Created, "location": The full filepath of the saved file.
400 BadRequest (with explanation)
404 NotFound (with explanation)

EobAttaches POST UploadSftp
Version Added: 24.3.7

Prior to running this method, upload a file to your own SFTP site. This method will then pull the uploaded file into the customer's AtoZ folder, database, or cloud storage. The filePath of the response object will either be the full filepath of the saved file (AtoZ or cloud) or blank (database).

ClaimPaymentNum: Required. FK to claimpayment.ClaimPaymentNum.
SftpAddress: Required. Specify the full path of the file (using /). The user with the SFTP credentials must have read permission in this directory.
SftpUsername: Required.
SftpPassword: Required.

Example Request:
POST /eobattaches/UploadSftp

{
"ClaimPaymentNum": 25,
"SftpAddress": "MySftpSite/myUsername/Documents/SmithJ_EOB_2024.png",
"SftpUsername": "myUsername",
"SftpPassword": "myPassword"
}

Example Response:
{
"EobAttachNum": 31,
"ClaimPaymentNum": 25,
"DateTCreated": "2024-10-14 09:17:43",
"FileName": "20241014_091743_15.jpg",
"RawBase64": ""
}

201 Created
400 BadRequest (with explanation)
404 NotFound (with explanation)