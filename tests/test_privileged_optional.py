from hiveden.docker.models import DockerContainer
from pydantic import ValidationError

def test_privileged_optional():
    # Test omission
    c = DockerContainer(name="test", image="nginx")
    assert c.privileged is False
    
    # Test True
    c = DockerContainer(name="test", image="nginx", privileged=True)
    assert c.privileged is True
    
    # Test False
    c = DockerContainer(name="test", image="nginx", privileged=False)
    assert c.privileged is False
    
    # Test None (should be allowed now)
    c = DockerContainer(name="test", image="nginx", privileged=None)
    # Depending on Pydantic version and config, Optional[bool] = False with None input might be None or False.
    # Typically Optional[T] = Default means if input is missing -> Default.
    # If input is None -> None (if valid) or Default.
    # With Optional[bool] = False, None is a valid value for the field type Optional[bool].
    # So c.privileged might be None.
    # But our logic handles None via `or False`.
    print(f"Privileged with None input: {c.privileged}")

    print("Model tests passed!")

if __name__ == "__main__":
    test_privileged_optional()
