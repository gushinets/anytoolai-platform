# Quota Model

MVP-A uses guest quota instead of billing.

Rules:

- check quota before scenario start;
- consume quota only after successful workflow result;
- failed workflow does not consume quota;
- quota exhausted returns standardized state;
- email capture and paywall intent are recorded.

The MVP-A conversion path is:

```text
guest usage -> quota exhausted -> email capture -> waitlist/paywall intent -> early access
```

Quota enforcement is backend-owned. Implementing guest quota only in frontend is an architecture error.
