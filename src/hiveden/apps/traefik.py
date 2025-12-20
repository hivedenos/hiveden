import json
import re
import urllib.request
import urllib.error
from typing import List, Optional, Union

from hiveden.config import config

class TraefikClient:
    def __init__(self, api_url: str = "http://traefik:8080"):
        self.api_url = api_url.rstrip("/")

    def _make_request(self, endpoint: str) -> Optional[Union[dict, list]]:
        url = f"{self.api_url}{endpoint}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            print(f"HTTP Error requesting {url}: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            print(f"URL Error requesting {url}: {e.reason}")
        except Exception as e:
            print(f"Error: {e}")
        return None

    def get_services(self) -> List[dict]:
        """Fetch all HTTP services."""
        data = self._make_request("/api/http/services")
        if isinstance(data, list):
            return data
        return []

    def get_service(self, service_name: str, provider: str = "docker") -> Optional[dict]:
        """Fetch specific service details."""
        # Traefik API uses the name as ID
        data = self._make_request(f"/api/http/services/{service_name}@{provider}")
        if isinstance(data, dict):
            return data
        return None

    def get_router(self, router_name: str, provider: str = "docker") -> Optional[dict]:
        """Fetch specific router details."""
        # Traefik API uses the name as ID
        data = self._make_request(f"/api/http/routers/{router_name}@{provider}")
        if isinstance(data, dict):
            return data
        return None

    def find_domains_for_router(self, router_name: str) -> List[str]:
        """
        Parse the router's rule to extract domains.
        Matches Host(`...`) rules.
        """
        router = self.get_router(router_name)
        if not router:
            return []
        
        rule = router.get("rule", "")
        if not rule:
            return []
            
        # Regex to capture content inside Host(`...`)
        # Traefik supports Host(`a`) or Host(`b`) etc.
        # Find all occurrences
        matches = re.findall(r"Host\(`([^`]+)`\)", rule)
        return matches

    def get_service_ip(self, service_name: str, provider: str = "docker") -> Optional[str]:
        """Fetch the IP address of a service."""
        service = self.get_service(service_name, provider)
        if not service:
            return None
        
        return service.get("loadBalancer", {}).get("servers", [{}])[0].get("url", "").split("://")[1].split(":")[0] 

def generate_traefik_labels(domain: str, port: int) -> dict:
    """
    Generate Traefik Docker labels for configuring ingress.
    
    Args:
        domain (str): The domain or subdomain.
        port (int): The port to expose.
        
    Returns:
        dict: A dictionary of Docker labels.
    """
    if "." in domain:
        full_domain = domain
    else:
        full_domain = f"{domain}.{config.domain}"
    
    # Sanitize domain for use as router/service name
    router_name = full_domain.split(".")[0].replace(".", "-")
    
    return {
        "traefik.enable": "true",
        f"traefik.http.routers.{router_name}.rule": f"Host(`{full_domain}`)",
        f"traefik.http.routers.{router_name}.entrypoints": "websecure,web",
        # f"traefik.http.routers.{router_name}.tls.certresolver": "myresolver",
        f"traefik.http.services.{router_name}.loadbalancer.server.port": str(port)
    }
