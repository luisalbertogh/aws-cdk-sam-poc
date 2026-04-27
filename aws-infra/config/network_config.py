"""
Network configuration for the AgentCore POC infrastructure.

All VPC and security-group settings are centralised here so that the stack
remains policy-agnostic and configuration changes never require touching
construct code.
"""

from dataclasses import dataclass, field

from aws_cdk import aws_ec2 as ec2


# ---------------------------------------------------------------------------
# Ingress rule descriptor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngressRule:
    """
    A single inbound security-group rule.

    Attributes
    ----------
    port:        TCP/UDP port number.
    description: Human-readable label shown in the AWS console.
    protocol:    ec2.Protocol — defaults to TCP.
    cidr:        Source CIDR block — defaults to the public Internet (0.0.0.0/0).
    """

    port: int
    description: str = ""
    protocol: ec2.Protocol = ec2.Protocol.TCP
    cidr: str = "0.0.0.0/0"


# ---------------------------------------------------------------------------
# Subnet configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubnetConfig:
    """
    Parameters for a single subnet tier inside the VPC.

    Attributes
    ----------
    name:       Logical name used as a tag and in CloudFormation resource IDs.
    subnet_type: PUBLIC or PRIVATE_WITH_EGRESS etc.
    cidr_mask:  Prefix length carved from the VPC CIDR.
                With a /27 VPC and cidr_mask=28, CDK creates two /28 subnets.
    """

    name: str = "Public"
    subnet_type: ec2.SubnetType = ec2.SubnetType.PUBLIC
    cidr_mask: int = 28


# ---------------------------------------------------------------------------
# Top-level network configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NetworkConfig:
    """Immutable configuration for the AgentCore POC network stack."""

    # -----------------------------------------------------------------------
    # VPC
    # -----------------------------------------------------------------------
    # /27 is the smallest CIDR block AWS allows for a VPC (32 IP addresses).
    # With two /28 subnets (16 IPs each) it is sufficient for this POC.
    vpc_cidr: str = "10.0.0.0/27"

    # Number of Availability Zones to spread subnets across (HA requirement).
    max_azs: int = 2

    # Disable the default NAT gateways — public subnets use the IGW directly.
    # (NAT gateways incur hourly cost; not needed here.)
    nat_gateways: int = 0

    # -----------------------------------------------------------------------
    # Subnets
    # -----------------------------------------------------------------------
    # One tier: two public subnets (one per AZ).
    # CDK creates the Internet Gateway, route tables, and associations
    # automatically when subnet_type=PUBLIC is present.
    subnets: tuple[SubnetConfig, ...] = field(
        default_factory=lambda: (SubnetConfig(),)
    )

    # -----------------------------------------------------------------------
    # Security group
    # -----------------------------------------------------------------------
    # Name used as the security-group description in the AWS console.
    security_group_name: str = "chef-ui-sg"

    # Inbound rules — add or remove entries here to change firewall policy.
    # All other inbound traffic is implicitly denied (AWS default).
    # Outbound is unrestricted by default (AWS default).
    inbound_rules: tuple[IngressRule, ...] = field(
        default_factory=lambda: (
            IngressRule(port=80,   description="HTTP"),
            IngressRule(port=443,  description="HTTPS"),
            IngressRule(port=8080, description="HTTP alternate"),
            IngressRule(port=8443, description="HTTPS alternate"),
        )
    )

    # -----------------------------------------------------------------------
    # Removal policy
    # -----------------------------------------------------------------------
    # VPCs contain no data, so DESTROY is safe for both dev and prod.
    # Change to "RETAIN" if you want to prevent accidental VPC deletion.
    removal_policy: str = "DESTROY"


# ---------------------------------------------------------------------------
# Singleton instance consumed by the stack
# ---------------------------------------------------------------------------
AGENTCORE_NETWORK_CONFIG = NetworkConfig()
