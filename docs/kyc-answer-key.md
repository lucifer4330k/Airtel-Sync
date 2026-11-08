# Smart KYC answer key (K01–K12)

Built by opening all 47 specimen images and checking each against the mock
GST and Udyam registries, the lead records and the case rules ("today" is
2026-07-15; address proof must be at most 90 days old). Enforced by
`apps/api/tests/kyc_answer_key/test_answer_key.py`, which runs the full
pipeline: OCR → field extraction → per-document checks → cross-document
checks → verdict.

| Applicant | Business | Finding | Verdict | Reason shown |
| --- | --- | --- | --- | --- |
| K01 | Vindhya Tours & Travels | GST registration is **Cancelled** in the registry; the Udyam certificate has a **blank registration number** | fail | "GST registration is Cancelled. It must be Active." / "The Udyam registration number is missing on this certificate." |
| K02 | Harmony Dental Care | Certificate **photographed at a ~5° tilt**; OCR reads `0` for `O` in the GSTIN | pass | Deskewed from text-box angles; GSTIN corrected by position (letters/digits are fixed slots) and checksum-verified |
| K03 | Ganesh Woodcraft | Clean | pass | |
| K04 | Saffron Dental Care LLP | GST certificate is **blurred** (sharpness 1 vs ~930+ for every other image) | fail | "The photo is too blurry to read. Please upload a sharper photo or scan." |
| K05 | Balaji Realty LLP | **Udyam certificate not uploaded**, though the business holds Udyam registration on file | incomplete | "Upload your Udyam certificate." |
| K06 | Saffron Unisex Salon | GSTIN `08YKZXS8189L1Z0` **fails the checksum** (printed that way; no OCR confusion explains it) | fail | "…not valid: GSTIN check digit is wrong (possible typo or tampering)." |
| K07 | Neelgiri Physio Clinic | Legal name **altered** on the certificate: "…(Prop. Shri Physio Clinic)" vs registry "…(Prop. Neelgiri Physio Clinic)" | fail | "Legal name on the certificate … does not match the GST registry …" |
| K08 | Green Leaf Legal Associates | OCR reads `0` for `O` in the GSTIN | pass | Corrected by position, checksum-verified |
| K09 | Kaveri Insurance Advisors | Clean | pass | |
| K10 | Kaveri Stays LLP | Signatory ID holder **Nisha Arora** is not the authorised contact on file (Fatima Menon) | review | "The ID holder … is not the authorised contact on file … A reviewer will confirm their authority to sign." |
| K11 | Trinity Bake House Pvt Ltd | Address proof dated **31 Oct 2025, 257 days old** | fail | "The bill is dated 31 Oct 2025, 257 days old. Upload one from the last 90 days." |
| K12 | Star Electronics | Clean | pass | |

## Deliberately not flagged

Udyam registration dates (and for some applicants the major activity) on the
certificates differ from the Udyam registry for **every** applicant, clean
ones included. That is generator noise, not a planted problem, so the
validator does not check those two fields.

## Checks the pipeline runs

Per document: image sharpness, document type (title), required fields
present, GSTIN format + checksum + registry status + legal name, Udyam
format + registry + enterprise name, ID expiry, bill date ≤ 90 days.

Across documents: same business on every document (fuzzy, proprietorship
aware), bill supply address = GST address, signatory = proprietor named on
the GST registration (proprietorships) or the contact on file (companies,
LLPs), GSTIN on the certificate = GSTIN the owner typed.

"review" never blocks the owner: it goes to the console's manual queue.
