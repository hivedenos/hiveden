from hiveden.docker.models import DockerContainer, HostConfig
from pydantic import ValidationError

def test_privileged_model():
    # Test default
    c = DockerContainer(name="test", image="nginx")
    assert c.privileged is False
    
    # Test True
    c = DockerContainer(name="test", image="nginx", privileged=True)
    assert c.privileged is True
    
    # Test HostConfig
    hc = HostConfig(NetworkMode="bridge")
    assert hc.Privileged is False
    
    hc = HostConfig(NetworkMode="bridge", Privileged=True)
    assert hc.Privileged is True

    print("Model tests passed!")

if __name__ == "__main__":
    test_privileged_model()
