"""easli — small, stateless helpers shared across services.

Keep modules here pure-function and dependency-light: no FastAPI, no Mongo,
no Mistral SDK imports. Anything that touches I/O belongs in `services/`.
"""
