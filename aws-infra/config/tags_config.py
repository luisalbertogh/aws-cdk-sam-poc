"""
Global AWS tag definitions for the AgentCore POC infrastructure.

All tag values are maintained here. Tags are applied at the CDK App level
in app.py so every resource in every stack inherits them automatically.
To update a value, change it here — no stack or construct code needs touching.
"""

# Key → value mapping applied to all deployed AWS resources.
COMMON_TAGS: dict[str, str] = {
    "Project": "Commission-Chef-Assistant",
    "Contact": "Daniel Parres",
    "Usage": "AgentCore POC",
}
