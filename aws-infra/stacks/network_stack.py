"""
NetworkStack — provisions the Chef UI VPC and security group.

Design decisions
----------------
- Smallest VPC CIDR (/27, 32 IPs): the Chef UI ECS service has a handful of
  tasks at most, so a /27 is more than sufficient and keeps the address space
  clean.  Two /27 public subnets are carved out (one per AZ).
- Public subnets only: the Chef UI is Internet-facing; no private subnets or
  NAT Gateways are needed, which avoids the ~$35/month NAT Gateway cost.
- Internet Gateway, route tables, and subnet-route associations are created
  automatically by the CDK Vpc L2 construct when subnet_type=PUBLIC is used.
- Security group: inbound rules are driven entirely by network_config.py so
  that port changes never require touching construct code.  All outbound
  traffic is allowed (CDK / AWS default).
- CfnOutputs: the VPC ID, both subnet IDs, and the security-group ID/ARN are
  exported so that downstream stacks (ECS, ALB, …) can import them without
  hard-coding resource IDs.
"""

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from config import AGENTCORE_NETWORK_CONFIG


class NetworkStack(cdk.Stack):
    """CDK stack that provisions the AgentCore POC VPC and security group."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        cfg = AGENTCORE_NETWORK_CONFIG

        removal_policy = (
            cdk.RemovalPolicy.RETAIN
            if cfg.removal_policy == "RETAIN"
            else cdk.RemovalPolicy.DESTROY
        )

        # -------------------------------------------------------------------
        # VPC
        #
        # CDK automatically provisions:
        #   - An Internet Gateway attached to the VPC
        #   - A public route table per AZ with a default route → IGW
        #   - Subnet-route-table associations
        # -------------------------------------------------------------------
        self.vpc = ec2.Vpc(
            self,
            "AgentCoreVpc",
            ip_addresses=ec2.IpAddresses.cidr(cfg.vpc_cidr),
            max_azs=cfg.max_azs,
            nat_gateways=cfg.nat_gateways,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name=subnet.name,
                    subnet_type=subnet.subnet_type,
                    cidr_mask=subnet.cidr_mask,
                )
                for subnet in cfg.subnets
            ],
        )

        # Apply removal policy to underlying CfnVpc resource.
        self.vpc.apply_removal_policy(removal_policy)

        # -------------------------------------------------------------------
        # Security group
        #
        # Inbound rules are defined in network_config.py (IngressRule entries).
        # Outbound is unrestricted — CDK / AWS default is allow-all egress.
        # -------------------------------------------------------------------
        self.security_group = ec2.SecurityGroup(
            self,
            "ChefUiSecurityGroup",
            vpc=self.vpc,
            security_group_name=cfg.security_group_name,
            description=f"Security group for the Chef UI ECS service ({cfg.security_group_name})",
            allow_all_outbound=True,
        )

        for rule in cfg.inbound_rules:
            self.security_group.add_ingress_rule(
                peer=ec2.Peer.ipv4(rule.cidr),
                connection=ec2.Port(
                    protocol=rule.protocol,
                    string_representation=f"port {rule.port}",
                    from_port=rule.port,
                    to_port=rule.port,
                ),
                description=rule.description,
            )

        # -------------------------------------------------------------------
        # Convenience references — public subnets resolved from the VPC
        # -------------------------------------------------------------------
        public_subnets = self.vpc.public_subnets

        # -------------------------------------------------------------------
        # Outputs
        # -------------------------------------------------------------------

        # VPC
        cdk.CfnOutput(
            self,
            "VpcId",
            value=self.vpc.vpc_id,
            description="ID of the AgentCore POC VPC",
            export_name=f"{self.stack_name}-VpcId",
        )

        cdk.CfnOutput(
            self,
            "VpcCidr",
            value=self.vpc.vpc_cidr_block,
            description="CIDR block of the AgentCore POC VPC",
            export_name=f"{self.stack_name}-VpcCidr",
        )

        # Public subnets — one output per subnet (indexed from 1)
        for idx, subnet in enumerate(public_subnets, start=1):
            cdk.CfnOutput(
                self,
                f"PublicSubnet{idx}Id",
                value=subnet.subnet_id,
                description=f"ID of public subnet {idx} ({subnet.availability_zone})",
                export_name=f"{self.stack_name}-PublicSubnet{idx}Id",
            )

            cdk.CfnOutput(
                self,
                f"PublicSubnet{idx}Az",
                value=subnet.availability_zone,
                description=f"Availability Zone of public subnet {idx}",
                export_name=f"{self.stack_name}-PublicSubnet{idx}Az",
            )

        # Comma-separated list for consumers that need all subnet IDs at once
        cdk.CfnOutput(
            self,
            "PublicSubnetIds",
            value=cdk.Fn.join(",", [s.subnet_id for s in public_subnets]),
            description="Comma-separated IDs of all public subnets",
            export_name=f"{self.stack_name}-PublicSubnetIds",
        )

        # Security group
        cdk.CfnOutput(
            self,
            "SecurityGroupId",
            value=self.security_group.security_group_id,
            description="ID of the Chef UI security group",
            export_name=f"{self.stack_name}-SecurityGroupId",
        )

        cdk.CfnOutput(
            self,
            "SecurityGroupArn",
            value=self.security_group.security_group_id,  # ARN == ID for SGs
            description="ARN of the Chef UI security group",
            export_name=f"{self.stack_name}-SecurityGroupArn",
        )

        cdk.CfnOutput(
            self,
            "SecurityGroupName",
            value=cfg.security_group_name,
            description="Name of the Chef UI security group",
            export_name=f"{self.stack_name}-SecurityGroupName",
        )
