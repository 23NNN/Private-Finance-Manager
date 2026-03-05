"""Security (Windows Desktop).

Contains:
- SQLCipher backend (crash-safe: DB stays encrypted during runtime)
- Security modes: NONE / PIN / DEVICE-LOCK (Windows DPAPI)
- Migration from legacy DBs (plaintext or DPAPI-wrapped)

Note:
- SQLCipher requires a DBAPI module (pysqlcipher3 or sqlcipher3).
"""
