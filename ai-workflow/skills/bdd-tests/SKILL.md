---
name: bdd-tests
description: Write backend tests that prove a spec's examples, as plain test functions with GIVEN/WHEN/THEN comments and `spec:` tags (no Gherkin or BDD library). Use when implementing a spec or ticket, writing tests test-first, or when another skill needs tests tied to spec examples.
---

# BDD tests

Every **example** in the spec's Examples tables becomes a test that proves it. Backend only.

## What a good test is

A test proves one example through a public interface and reads like its row. See [tests.md](../tdd/tests.md) for good tests and anti-patterns, and [mocking.md](../tdd/mocking.md) for mocking.

```python
@pytest.mark.parametrize("days", [1, 29])
def test_return_within_window_refunds_cash(client, clock, days):
    # spec: 1.1-b
    # GIVEN a £40 kettle bought <days> days ago
    order = client.post("/orders", json={"item": "kettle", "price": 4000}).json()
    clock.advance(days=days)

    # WHEN the customer returns it
    response = client.post(f"/orders/{order['id']}/return")

    # THEN the customer gets £40 cash and no store credit
    assert response.status_code == 200
    assert response.json() == {"cash_refund": 4000, "store_credit": 0}
```

Keep test code straight-line: parameters take the place of `if`, `for`, and `try`.

## Seams: where tests go

The spec's External interface names the agreed seams. Test through the highest one (HTTP, CLI, consumer), in-process against a test database. Use a lower public interface only when the external one cannot arrange the GIVEN, and say why in a comment.

## Rules of the loop

- **Red first for ✅ rows.** Watch the test fail for the expected reason. For a bug, the red repro becomes the Expected row's test.
- **One example at a time**, as a tracer bullet.
- **Extend before you add.** Change an existing expected value or delete a test only when an approved example changes that behaviour.

Done when every example ID in the spec appears in a `spec:` tag, every test is green, and every ✅ test was seen red.
