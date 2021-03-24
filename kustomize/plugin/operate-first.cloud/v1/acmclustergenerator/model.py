import ipaddress

from pydantic import BaseModel, AnyUrl
from typing import Optional, List, Dict, Union


class Metadata(BaseModel):
    name: str
    namespace: Optional[str]
    labels: Optional[Dict[str, str]]
    annotations: Optional[Dict[str, str]]


class Object(BaseModel):
    apiVersion: str
    kind: str
    metadata: Metadata


class Namespace(Object):
    apiVersion: str = 'v1'
    kind: str = 'Namespace'


class Secret(Object):
    apiVersion: str = 'v1'
    kind: str = 'Secret'

    type: str = 'Opaque'
    stringData: Optional[Dict[str, str]]
    data: Optional[Dict[str, str]]


class kacEnabledSetting(BaseModel):
    enabled: bool = True


class kacApplicationManager(kacEnabledSetting):
    argocdCluster: bool = False


class kacSpec(BaseModel):
    clusterName: str
    clusterNamespace: str
    clusterLabels: Optional[Dict[str, str]]
    applicationManager: kacApplicationManager = kacApplicationManager()
    policyController: kacEnabledSetting = kacEnabledSetting()
    searchCollector: kacEnabledSetting = kacEnabledSetting()
    certPolicyController: kacEnabledSetting = kacEnabledSetting()
    iamPolicyController: kacEnabledSetting = kacEnabledSetting()
    version: str = '2.2.0'


class KlusterletAddonConfig(Object):
    apiVersion: str = 'agent.open-cluster-management.io/v1'
    kind: str = 'KlusterletAddonConfig'
    spec: kacSpec


class managedClusterSpec(BaseModel):
    hubAcceptsClient: bool = True


class ManagedCluster(Object):
    apiVersion: str = 'cluster.open-cluster-management.io/v1'
    kind: str = 'ManagedCluster'
    spec: managedClusterSpec = managedClusterSpec()


class icControl(BaseModel):
    name: str = 'master'
    replicas: int = 0
    platform: dict = {'baremetal': {}}


class icCompute(BaseModel):
    name: str = 'worker'
    replicas: int = 0


class cidrAddress(BaseModel):
    cidr: ipaddress.IPv4Network
    hostPrefix: Optional[int]


class icNetworking(BaseModel):
    clusterNetwork: List[cidrAddress]
    machineCIDR: ipaddress.IPv4Network
    networkType: str = 'OpenShiftSDN'
    serviceNetwork: List[ipaddress.IPv4Network]


class baremetalBMC(BaseModel):
    address: AnyUrl
    disableCertificateVerification: bool = True
    username: Optional[str]
    password: Optional[str]


class baremetalHostBase(BaseModel):
    name: str
    role: str
    bmc: baremetalBMC
    bootMACAddress: str


class icBaremetalHost(baremetalHostBase):
    namespace: str


class baremetalPlatformBase(BaseModel):
    libvirtURI: AnyUrl
    provisioningNetworkCIDR: ipaddress.IPv4Network
    provisioningNetworkInterface: str
    provisioningBridge: str = 'provisioning'
    externalBridge: str = 'baremetal'


class icBaremetalPlatform(baremetalPlatformBase):
    hosts: List[icBaremetalHost]
    apiVIP: ipaddress.IPv4Address
    ingressVIP: ipaddress.IPv4Address


class icBaremetalPlatformContainer(BaseModel):
    baremetal: icBaremetalPlatform


class InstallConfig(BaseModel):
    apiVersion: str = 'v1'
    metadata: Metadata
    baseDomain: str
    controlPlane: icControl
    compute: List[icCompute]
    networking: icNetworking
    pullSecret: str = ''
    sshKey: str

    # marked as a Union in case we want to add support for
    # non-baremetal platforms
    platform: Union[icBaremetalPlatformContainer]


class nameRef(BaseModel):
    name: str


class cdProvisioning(BaseModel):
    imageSetRef: nameRef
    installConfigSecretRef: nameRef
    sshPrivateKeySecretRef: nameRef

    sshKnownHosts: List[str]


class cdBaremetalPlatform(BaseModel):
    libvirtSSHPrivateKeySecretRef: nameRef
    hosts: List[icBaremetalHost]


class cdBaremetalPlatformContainer(BaseModel):
    baremetal: cdBaremetalPlatform


class clusterDeploymentSpec(BaseModel):
    baseDomain: str
    clusterName: str
    controlPlaneConfig: dict = {'servingCertificates': {}}
    installAttemptsLimit: int = 2
    installed: bool = False
    provisioning: cdProvisioning
    platform: Union[cdBaremetalPlatformContainer]
    pullSecretRef: nameRef


class ClusterDeployment(Object):
    apiVersion: str = 'hive.openshift.io/v1'
    kind: str = 'ClusterDeployment'
    spec: clusterDeploymentSpec


class opfSshInfo(BaseModel):
    sshKnownHosts: List[str]
    sshPublicKey: str
    sshPrivateKey: str


class opfBaremetalHost(baremetalHostBase):
    pass


class opfBaremetal(BaseModel):
    bmcUsername: str
    bmcPassword: str
    disableCertificateVerification: bool = True
    hosts: List[opfBaremetalHost]


class opfNetworking(icNetworking):
    apiVIP: ipaddress.IPv4Address
    ingressVIP: ipaddress.IPv4Address


class opfProvisioning(baremetalPlatformBase):
    imageSetRef: nameRef


class opfClusterDeploymentSpec(BaseModel):
    baseDomain: str
    clusterName: str
    enableArgoCd: bool = True

    networking: opfNetworking
    provisioning: opfProvisioning
    baremetal: opfBaremetal
    ssh: opfSshInfo
    pullSecret: str


class opfClusterDeployment(BaseModel):
    apiVersion: str = 'operate-first.cloud/v1'
    kind: str = 'acmClusterGenerator'
    spec: opfClusterDeploymentSpec


class providerConnection(BaseModel):
    imageMirror: Optional[AnyUrl]
    bootstrapOSImage: Optional[AnyUrl]
    clusterOSImage: Optional[AnyUrl]
    additionalTrustBundle: Optional[str]
    baseDomain: str
    libvirtURI: AnyUrl
    pullSecret: str
    sshPrivateKey: str
    sshPublicKey: str
    sshKnownHosts: List[str]
    isOcp: bool = True
