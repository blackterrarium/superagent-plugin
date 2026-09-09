Synthetic validation fixture revision fixture-v1. This is a test scenario, not a real user PRD approval.
SC1: Malformed JSON is rejected with ValueError and preserves existing destination bytes. Scope: only this malformed-input behavior.
C1: python3 test_positive.py (positive), python3 test_negative.py (negative), exit 0; timeout 1 minute.
J1: Inspect the test to verify that an executed assertion distinguishes unchanged destination bytes from mere destination existence. Evidence: product.py and the selected test file.
AC1 | SC1 | malformed JSON with preexisting destination | ValueError and unchanged bytes | C1 executes; J1 inspects exception and exact byte equality assertions.
Approval assumption for this synthetic scenario: fixture author approved precisely fixture-v1. Optional gzip support remains unapproved.
