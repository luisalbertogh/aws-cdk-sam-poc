"""
Global AWS tag definitions for the Cloud POC infrastructure.

All tag values are maintained here. Tags are applied at the CDK App level
in app.py so every resource in every stack inherits them automatically.
To update a value, change it here — no stack or construct code needs touching.
"""

# Key → value mapping applied to all deployed AWS resources.
COMMON_TAGS: dict[str, str] = {
    "Project": "Cloud POC",
    "Contact": "Luis Alberto Garcia Hernandez",
    "Usage": "Cloud POC",
}
