"""Dispute letter templates for the Credit Repair Cloud MVP.

Templates use Python str.format() style placeholders. Call `render()` to merge
client/item/dispute context into a template body.
"""

from datetime import date


PERSONAL_TEMPLATES: dict[str, str] = {
    "Round 1 - General Dispute (FCRA §611)": """\
{today}

{client_name}
{client_address}
{client_city}, {client_state} {client_zip}

{bureau}
Consumer Dispute Center

To Whom It May Concern,

I am writing to dispute inaccurate information appearing on my credit report,
pursuant to Section 611 of the Fair Credit Reporting Act (15 U.S.C. §1681i).

The following item is inaccurate or incomplete and I request its investigation
and removal:

    Creditor / Furnisher : {creditor}
    Account Number       : {account_number}
    Item Type            : {item_type}

Reason for dispute:
{reason}

Please investigate this matter and provide me with the results within 30 days
as required by the FCRA. If the information cannot be verified, it must be
deleted from my file.

Sincerely,

{client_name}
SSN: XXX-XX-{ssn_last4}
DOB: {dob}
""",

    "Round 2 - Escalation / Method of Verification": """\
{today}

{client_name}
{client_address}
{client_city}, {client_state} {client_zip}

{bureau}
Consumer Dispute Center

Re: Follow-up on prior dispute

To Whom It May Concern,

I previously disputed the account listed below and your office responded that
the information was "verified." I am now exercising my right under 15 U.S.C.
§1681i(a)(6)(B)(iii) to request a full description of the Method of
Verification used, including:

  1. The name, address, and telephone number of every person contacted.
  2. Copies of any documents used to verify the account.
  3. The specific procedure followed in reaching your conclusion.

Disputed item:

    Creditor / Furnisher : {creditor}
    Account Number       : {account_number}
    Item Type            : {item_type}

If the account cannot be fully and properly verified, it must be deleted from
my credit file immediately.

Sincerely,

{client_name}
SSN: XXX-XX-{ssn_last4}
""",

    "FCRA §609 - Request for Information": """\
{today}

{client_name}
{client_address}
{client_city}, {client_state} {client_zip}

{bureau}
Consumer Dispute Center

To Whom It May Concern,

Pursuant to Section 609 of the Fair Credit Reporting Act, I am requesting that
you provide me with copies of any and all documentation you have on file that
authorizes the following account to be reported on my consumer credit report.

    Creditor / Furnisher : {creditor}
    Account Number       : {account_number}

If you cannot provide signed documentation bearing my signature, please delete
this item from my report in accordance with the FCRA.

Sincerely,

{client_name}
SSN: XXX-XX-{ssn_last4}
""",

    "Debt Validation (FDCPA §809)": """\
{today}

{client_name}
{client_address}
{client_city}, {client_state} {client_zip}

{creditor}
Attn: Collections Department

Re: Account #{account_number}

To Whom It May Concern,

This letter is sent in response to a notice received from your company. Under
Section 809(b) of the Fair Debt Collection Practices Act, I am requesting
validation of this debt, specifically:

  1. Proof that you own the debt or are authorized to collect.
  2. The original signed contract creating the obligation.
  3. A complete payment and transaction history.
  4. Proof of your license to collect in my state.

Until this debt is validated, you must cease all collection activity and
reporting to the credit bureaus. Please respond in writing only.

Sincerely,

{client_name}
""",

    "Goodwill Letter": """\
{today}

{client_name}
{client_address}
{client_city}, {client_state} {client_zip}

{creditor}
Customer Service

Re: Account #{account_number}

Dear Goodwill Department,

I have been a customer of yours and value the relationship. Unfortunately, my
account shows a {item_type} that resulted from a temporary hardship. I have
since resolved the matter and maintained my account in good standing.

I am respectfully requesting a goodwill adjustment removing this mark from my
credit report. This single item is holding back a major life goal, and your
help would mean a great deal.

Thank you for your consideration.

Sincerely,

{client_name}
""",
}


BUSINESS_TEMPLATES: dict[str, str] = {
    "Business Credit Dispute - General": """\
{today}

{client_name}
{client_address}
{client_city}, {client_state} {client_zip}
EIN: {ein}

{bureau}
Commercial Credit Dispute Department

To Whom It May Concern,

{client_name} is disputing inaccurate information appearing on our business
credit file with {bureau}. The following tradeline is inaccurate and we
request its investigation and removal:

    Creditor / Furnisher : {creditor}
    Account Number       : {account_number}
    Item Type            : {item_type}

Reason for dispute:
{reason}

Please investigate and correct or delete the disputed tradeline and send us
an updated business credit report.

Sincerely,

{signer_name}, Authorized Representative
{client_name}
""",

    "Business Tradeline Verification Request": """\
{today}

{client_name}
{client_address}
{client_city}, {client_state} {client_zip}
EIN: {ein}

{bureau}
Commercial Credit Department

To Whom It May Concern,

We are requesting full verification of the following tradeline reporting on
our business credit file. Please provide the method of verification used,
the data furnisher's contact information, and supporting documentation.

    Creditor / Furnisher : {creditor}
    Account Number       : {account_number}

If verification cannot be provided, please remove this tradeline from our
business credit profile.

Sincerely,

{signer_name}, Authorized Representative
{client_name}
""",
}


def all_templates(client_type: str) -> dict[str, str]:
    return PERSONAL_TEMPLATES if client_type == "Personal" else BUSINESS_TEMPLATES


def render(template_body: str, context: dict) -> str:
    """Merge the context dict into the template, tolerating missing keys."""
    defaults = {
        "today": date.today().strftime("%B %d, %Y"),
        "client_name": "",
        "client_address": "",
        "client_city": "",
        "client_state": "",
        "client_zip": "",
        "bureau": "",
        "creditor": "",
        "account_number": "",
        "item_type": "",
        "reason": "",
        "ssn_last4": "____",
        "dob": "",
        "ein": "",
        "signer_name": "",
    }
    defaults.update({k: ("" if v is None else str(v)) for k, v in context.items()})
    try:
        return template_body.format(**defaults)
    except KeyError as exc:
        return template_body + f"\n\n[Template error: missing key {exc}]"
