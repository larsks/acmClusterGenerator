#!/usr/bin/python

import base64
import ipaddress
import pydantic
import sys
import yaml

from . import model


def str_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data))


def maybe_use_block(dumper, data):
    style = '|' if '\n' in data else None
    return dumper.represent_scalar('tag:yaml.org,2002:str', str(data), style=style)


def fill_host_defaults(host, opf):
    if 'username' not in host.bmc:
        host.bmc.username = opf.spec.baremetal.bmcUsername
    if 'password' not in host.bmc:
        host.bmc.password = opf.spec.baremetal.bmcPassword

    return model.icBaremetalHost(
        namespace=opf.spec.clusterName,
        **host.dict()
    )


def register_representers():
    yaml.SafeDumper.add_representer(ipaddress.IPv4Network, str_representer)
    yaml.SafeDumper.add_representer(ipaddress.IPv4Address, str_representer)
    yaml.SafeDumper.add_representer(pydantic.AnyUrl, str_representer)
    yaml.SafeDumper.add_representer(str, maybe_use_block)


def main():
    register_representers()

    with open(sys.argv[1]) as fd:
        opf = model.opfClusterDeployment.parse_obj(yaml.safe_load(fd))

    docs = []

    docs.append(
        model.Namespace(
            metadata=model.Metadata(
                name=opf.spec.clusterName,
            )
        )
    )

    docs.append(
        model.KlusterletAddonConfig(
            metadata=model.Metadata(
                name=opf.spec.clusterName,
                namespace=opf.spec.clusterName,
            ),
            spec=model.kacSpec(
                clusterName=opf.spec.clusterName,
                clusterNamespace=opf.spec.clusterName,
                clusterLabels={
                    'cloud': 'Bare-Metal',
                    'vendor': 'OpenShift',
                },
                applicationManager=model.kacApplicationManager(
                    argocdCluster=opf.spec.enableArgoCd,
                )
            ),
        )
    )

    docs.append(
        model.ManagedCluster(
            metadata=model.Metadata(
                name=opf.spec.clusterName,
                labels={
                    'cloud': 'Bare-Metal',
                    'name': opf.spec.clusterName,
                    'vendor': 'OpenShift',
                }
            ),
        )
    )

    docs.append(
        model.Secret(
            metadata=model.Metadata(
                name=f'{opf.spec.clusterName}-pull-secret',
                namespace=opf.spec.clusterName,
            ),
            type='kubernetes.io/dockerconfigjson',
            stringData={
                '.dockerconfigjson': opf.spec.pullSecret,
            }
        )
    )

    docs.append(
        model.Secret(
            metadata=model.Metadata(
                name=f'{opf.spec.clusterName}-ssh-private-key',
                namespace=opf.spec.clusterName,
            ),
            stringData={
                'ssh-privatekey': opf.spec.ssh.sshPrivateKey,
            },
        )
    )


    # providerconnection = model.providerConnection(
    #     baseDomain=opf.spec.baseDomain,
    #     libvirtURI=opf.spec.provisioning.libvirtURI,
    #     pullSecret=opf.spec.pullSecret,
    #     sshPrivateKey=opf.spec.ssh.sshPrivateKey,
    #     sshPublicKey=opf.spec.ssh.sshPublicKey,
    #     sshKnownHosts=opf.spec.ssh.sshKnownHosts,
    # )
    #
    # docs.append(
    #     model.Secret(
    #         metadata=model.Metadata(
    #             name=f"{opf.spec.clusterName}-libvirt-connection",
    #             namespace=opf.spec.clusterName,
    #             labels={
    #                 'cluster.open-cluster-management.io/cloudconnection': '',
    #                 'cluster.open-cluster-management.io/provider': 'bmc',
    #             },
    #         ),
    #         stringData={
    #             "metadata": base64.encodebytes(
    #                 yaml.safe_dump(providerconnection.dict(exclude_none=True)).encode()
    #             )
    #         },
    #     )
    # )


    installconfig = model.InstallConfig(
        metadata=model.Metadata(
            name=opf.spec.clusterName,
        ),
        baseDomain=opf.spec.baseDomain,
        controlPlane=model.icControl(
            replicas=len([
                host for host in opf.spec.baremetal.hosts
                if host.role == 'master'
            ])
        ),
        compute=[
            model.icCompute(
                replicas=len([
                    host for host in opf.spec.baremetal.hosts
                    if host.role == 'worker'
                ])
            )
        ],
        networking=model.icNetworking(
            clusterNetwork=opf.spec.networking.clusterNetwork,
            machineCIDR=opf.spec.networking.machineCIDR,
            networkType=opf.spec.networking.networkType,
            serviceNetwork=opf.spec.networking.serviceNetwork
        ),
        platform=model.icBaremetalPlatformContainer(
            baremetal=model.icBaremetalPlatform(
                libvirtURI=opf.spec.provisioning.libvirtURI,
                provisioningNetworkCIDR=opf.spec.provisioning.provisioningNetworkCIDR,
                provisioningNetworkInterface=opf.spec.provisioning.provisioningNetworkInterface,
                provisioningBridge=opf.spec.provisioning.provisioningBridge,
                externalBridge=opf.spec.provisioning.externalBridge,
                apiVIP=opf.spec.networking.apiVIP,
                ingressVIP=opf.spec.networking.ingressVIP,
                hosts=[
                    fill_host_defaults(host, opf)
                    for host in opf.spec.baremetal.hosts
                ],
            )
        ),
        sshKey=opf.spec.ssh.sshPublicKey,
        pullSecret='',
    )

    docs.append(
        model.Secret(
            metadata=model.Metadata(
                name=f'{opf.spec.clusterName}-install-config',
                namespace=opf.spec.clusterName,
            ),
            data={
                "install-config.yaml": base64.encodebytes(
                    yaml.safe_dump(installconfig.dict(exclude_none=True)).encode()
                )
            }
        )
    )

    docs.append(
        model.ClusterDeployment(
            metadata=model.Metadata(
                name=opf.spec.clusterName,
                namespace=opf.spec.clusterName,
                labels={
                    'cloud': 'BMC',
                    'vendor': 'OpenShift',
                },
                annotations={
                    'hive.openshift.io/try-install-once': 'true',
                }
            ),
            spec=model.clusterDeploymentSpec(
                baseDomain=opf.spec.baseDomain,
                clusterName=opf.spec.clusterName,
                platform=model.cdBaremetalPlatformContainer(
                    baremetal=model.cdBaremetalPlatform(
                        libvirtSSHPrivateKeySecretRef=model.nameRef(
                            name=f'{opf.spec.clusterName}-ssh-private-key',
                        ),
                        hosts=[
                            fill_host_defaults(host, opf)
                            for host in opf.spec.baremetal.hosts
                        ],
                    )
                ),
                provisioning=model.cdProvisioning(
                    imageSetRef=opf.spec.provisioning.imageSetRef,
                    installConfigSecretRef=model.nameRef(
                        name=f'{opf.spec.clusterName}-install-config',
                    ),
                    sshPrivateKeySecretRef=model.nameRef(
                        name=f'{opf.spec.clusterName}-ssh-private-key',
                    ),
                    sshKnownHosts=opf.spec.ssh.sshKnownHosts,
                ),
                pullSecretRef=model.nameRef(
                    name=f'{opf.spec.clusterName}-pull-secret',
                )
            )
        )
    )

    yaml.safe_dump_all((doc.dict(exclude_none=True) for doc in docs),
                       stream=sys.stdout)
