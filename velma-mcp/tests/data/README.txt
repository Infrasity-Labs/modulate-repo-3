Every JSON file here (not in real/) is derived from the OpenAPI spec examples, not captured from the live API.
Where a spec gives no example value (for instance the extra frames in synthetic.json, and
all of batch.json, whose spec has no 200 example), the values follow the schema types and enums
and were chosen only for tests. Each file carries a "_comment" key; the test loader drops it.
