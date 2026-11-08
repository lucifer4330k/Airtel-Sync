# 3-minute demo script

Setup before recording:
- **Data and the demo order:** run `seed_db.py`. It prints a demo tracker link.
- **Windows:** open two browser windows, the phone-size owner app (375 × 812) and the console, signed in as `admin`.
- **LLM:** optionally set `GOOGLE_API_KEY` for warmer Hinglish phrasing; the flow is identical without it.

| Time | Screen | What to do / say |
| --- | --- | --- |
| 0:00–0:20 | Landing → funnel (or Console → Funnel) | Point at the red ends of the 3D funnel: "7.4% of leads activate, it takes 17.6 days, and costs about ₹15,000 each. Owners chase us 3 times. Here's the journey without the wait." |
| 0:20–0:50 | Owner app → Advisor | Type: *"Hum ek dental clinic chalate hain Pune mein, 8 log hain, GST hai, internet bahut jata hai"*. The advisor replies in Hinglish, asks for the GSTIN (paste K03's or any Active one), and builds the Smart Office plan with reasons ("1 site, failover keeps billing running"). Open the plan. |
| 0:50–1:20 | Quote → "What if my budget or needs change?" | **Hand the judge the controls.** Set a budget below the plan, add Backup 4G/5G Failover: the app names the gap and finds the smallest fix. Mark backup essential: it shows the trade-off and asks the owner to choose. Switch the connection to 5G AirFiber: it explains backup needs a fixed line and offers staying on fibre or a specialist who keeps the need on file. |
| 1:20–1:55 | Checkout → Documents | Enter a mobile number, choose UPI AutoPay, pay setup. KYC consent screen, then the GSTIN auto-fills from the registry. Upload K03's GST, Udyam and ID, then **K11's address proof**: it's caught live as "257 days old". Re-upload K03's bill and it passes. (Show the DigiLocker / e-sign step as the mocked screen.) |
| 1:55–2:25 | Tracker + Console → Orders | The order moved to "Documents verified" by itself. In the console, click **Advance**: engineer visit booked. The tracker updates within seconds, and the WhatsApp message shows in the outbox. |
| 2:25–2:50 | Console → Leads | "Waiting for a call" view: a lead that asked for a leased line (site survey) or a human, its likelihood score and top three reasons. Assign it to the Pune rep. Then the KYC review queue: approve K10's signatory with a note. |
| 2:50–3:00 | Back to Funnel | "Answers in two minutes, documents checked while you wait, zero visits to sign up: the digital journey cuts the follow-up calls to zero and the cost per activation with them." |

Pitch line: *"Give us a customer whose first order falls apart. We'll show you how they still buy an eligible bundle without starting over."* Then let the judge use `/judge` to break any scenario they like; every option they see is re-checked by the rules engine, and the scorecard below it shows the measured results.

Backup if anything fails live:
- **Advisor:** `tests/advisor_scenarios/personas.yaml` replays 27 personas.
- **KYC:** `tests/kyc_answer_key` replays K01–K12.
