import os
import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Detectie markers voor verschillende applicatietypes
# Simpel: alleen PHP, Node.js, Python en HTML
DETECTION_MARKERS = {
    "php": {
        "files": ["composer.json"],
        "extensions": [".php"],
        "web_servers": ["apache"],
        "runtime": None,  # PHP draait in Apache
        "db_drivers": ["pdo_mysql", "pdo_pgsql", "mysqli"]
    },
    "nodejs": {
        "files": ["package.json"],
        "extensions": [".js"],
        "web_servers": ["nginx"],
        "runtime": "node",
        "api_frameworks": ["express"]
    },
    "python": {
        "files": ["requirements.txt"],
        "extensions": [".py"],
        "web_servers": ["nginx"],
        "runtime": "python",
        "api_frameworks": ["fastapi", "flask", "django"],
        "db_drivers": ["psycopg2", "mysql-connector"]
    },
    "html": {
        "files": ["index.html"],
        "extensions": [".html", ".htm"],
        "web_servers": ["nginx"],
        "runtime": None,
        "static": True
    }
}

# Database detectie markers - MySQL, PostgreSQL en InfluxDB
DB_MARKERS = {
    "mysql": {
        "keywords": ["mysql"],
        "drivers": ["mysql-connector", "pymysql", "mysqli", "pdo_mysql"],
        "config_patterns": ["mysql://"]
    },
    "postgresql": {
        "keywords": ["postgres", "postgresql"],
        "drivers": ["psycopg2", "pg", "postgres"],
        "config_patterns": ["postgres://", "postgresql://"]
    },
    "influxdb": {
        "keywords": ["influxdb", "influx"],
        "drivers": ["influxdb-client", "influx"],
        "config_patterns": ["influxdb://"]
    }
}


def _analyze_directory(directory: str) -> Dict:
    """Analyseer een directory en detecteer applicatietype en benodigde containers."""
    path = Path(directory)
    if not path.exists():
        logger.error(f"Directory bestaat niet: {directory}")
        return {"error": f"Directory bestaat niet: {directory}"}

    results = {
        "app_type": "unknown",
        "containers": {
            "web": [],
            "api": [],
            "db": []
        },
        "detected_files": [],
        "detected_frameworks": [],
        "detected_databases": [],
        "confidence": 0
    }

    detected_types = []
    all_files = []
    
    # Verzamel alle bestanden
    try:
        for root, dirs, files in os.walk(directory):
            # Skip node_modules, venv, etc.
            dirs[:] = [d for d in dirs if d not in ['.git', 'node_modules', 'venv', '__pycache__', '.venv']]
            for file in files:
                file_path = Path(root) / file
                relative_path = file_path.relative_to(path)
                all_files.append(str(relative_path))
    except Exception as e:
        logger.error(f"Fout bij lezen van directory: {e}")
        return {"error": str(e)}

    # Detecteer applicatietype - simpel: check op marker bestanden
    detection_order = ["php", "nodejs", "python", "html"]
    
    for app_type in detection_order:
        if app_type not in DETECTION_MARKERS:
            continue
            
        markers = DETECTION_MARKERS[app_type]
        score = 0
        found_files = []
        
        # Simpel: check of marker bestand bestaat
        for marker_file in markers.get("files", []):
            if marker_file in all_files:
                score = 100  # Als marker bestand gevonden, 100% zeker
                found_files.append(marker_file)
                break  # Stop na eerste match
        
        # Als geen marker bestand, check extensies
        if score == 0:
            for ext in markers.get("extensions", []):
                if any(f.lower().endswith(ext.lower()) for f in all_files):
                    score = 50  # Extensie gevonden = 50% zeker
                    break
        
        if score > 0:
            detected_types.append({
                "type": app_type,
                "score": score,
                "found_files": found_files
            })
            results["detected_files"].extend(found_files)

    # Als er geen specifieke markers zijn maar wel HTML bestanden, gebruik HTML
    if not detected_types:
        html_files = [f for f in all_files if f.lower().endswith((".html", ".htm"))]
        if html_files:
            detected_types.append({
                "type": "html",
                "score": 50,
                "found_files": [html_files[0]]
            })
            results["detected_files"].append(html_files[0])
    
    if detected_types:
        # Simpel: neem het type met hoogste score
        best_match = max(detected_types, key=lambda x: x["score"])
        results["app_type"] = best_match["type"]
        results["confidence"] = best_match["score"]
        logger.info(f"Gedetecteerd applicatietype: {results['app_type']} (confidence: {results['confidence']}%)")
    else:
        # Geen type gedetecteerd - retourneer "unknown"
        results["app_type"] = "unknown"
        results["confidence"] = 0
        logger.warning(f"Geen applicatietype gedetecteerd - retourneer 'unknown'")

    # Analyseer configuratiebestanden voor frameworks en databases
    # ALTIJD scannen voor WEB, API & DB - ongeacht applicatietype
    if results["app_type"] != "unknown":
        markers = DETECTION_MARKERS[results["app_type"]]
        
        # Check voor frameworks (simpel: alleen Node.js en Python)
        if results["app_type"] == "nodejs":
            _detect_nodejs_frameworks(path, results, markers)
        elif results["app_type"] == "python":
            _detect_python_frameworks(path, results, markers)
        
        # Voeg runtime containers toe (niet voor statische HTML sites)
        runtime = markers.get("runtime")
        if runtime and not markers.get("static", False):
            if results["app_type"] in ["nodejs", "python"]:
                results["containers"]["api"].append({
                    "type": runtime,
                    "image": _get_runtime_image(results["app_type"], runtime),
                    "reason": f"Runtime voor {results['app_type']} applicatie"
                })
        
        # Voeg web servers toe
        # Voor HTML/statische sites: altijd nginx gebruiken
        web_servers = markers.get("web_servers", [])
        if results["app_type"] == "html" and "nginx" not in web_servers:
            web_servers = ["nginx"]  # Forceer nginx voor HTML sites
        
        # Voeg alle webservers toe (meestal maar één)
        for web_server in web_servers:
            results["containers"]["web"].append({
                "type": web_server,
                "image": _get_web_server_image(web_server),
                "reason": f"Web server voor {results['app_type']} applicatie"
            })

    # ALTIJD databases detecteren - ook voor HTML sites (kan backend API hebben)
    _detect_databases(path, all_files, results)

    return results


def _detect_nodejs_frameworks(path: Path, results: Dict, markers: Dict):
    """Detecteer Node.js frameworks."""
    package_json_path = path / "package.json"
    if package_json_path.exists():
        try:
            with open(package_json_path, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
                if not isinstance(package_data, dict):
                    logger.warning(f"package.json is geen dict maar {type(package_data)}")
                    return
                dependencies = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
                
                # Check voor API frameworks
                for framework in markers.get("api_frameworks", []):
                    if framework in dependencies:
                        results["detected_frameworks"].append(framework)
                        logger.info(f"Gedetecteerd API framework: {framework}")
                
                # Check voor web frameworks
                for framework in markers.get("web_frameworks", []):
                    if framework in dependencies:
                        results["detected_frameworks"].append(framework)
                        logger.info(f"Gedetecteerd web framework: {framework}")
        except json.JSONDecodeError as e:
            logger.warning(f"Kon package.json niet parsen als JSON: {e}")
        except Exception as e:
            logger.warning(f"Kon package.json niet lezen: {e}")


def _detect_python_frameworks(path: Path, results: Dict, markers: Dict):
    """Detecteer Python frameworks."""
    requirements_path = path / "requirements.txt"
    if requirements_path.exists():
        try:
            with open(requirements_path, 'r', encoding='utf-8') as f:
                requirements = f.read().lower()
                
                for framework in markers.get("api_frameworks", []):
                    if framework in requirements:
                        results["detected_frameworks"].append(framework)
                        logger.info(f"Gedetecteerd framework: {framework}")
        except Exception as e:
            logger.warning(f"Kon requirements.txt niet lezen: {e}")


def _detect_databases(path: Path, all_files: List[str], results: Dict):
    """Detecteer gebruikte databases - ALTIJD uitgevoerd voor alle applicatietypes."""
    detected_dbs = set()
    
    # Check configuratiebestanden (simpel: alleen .env en config.json)
    config_files = [".env", "config.json"]
    
    for config_file in config_files:
        config_path = path / config_file
        if config_path.exists():
            try:
                content = config_path.read_text(encoding='utf-8', errors='ignore').lower()
                for db_type, db_markers in DB_MARKERS.items():
                    # Check config patterns
                    for pattern in db_markers.get("config_patterns", []):
                        if pattern in content:
                            detected_dbs.add(db_type)
                            logger.info(f"Database gedetecteerd via config bestand {config_file}: {db_type}")
                    # Check keywords
                    for keyword in db_markers.get("keywords", []):
                        if keyword in content:
                            detected_dbs.add(db_type)
                            logger.info(f"Database gedetecteerd via keyword in {config_file}: {db_type}")
            except Exception as e:
                logger.warning(f"Kon config bestand {config_file} niet lezen: {e}")
    
    # Check dependencies op basis van applicatietype
    app_type = results.get("app_type", "unknown")
    
    if app_type == "nodejs":
        package_json_path = path / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                    if not isinstance(package_data, dict):
                        logger.warning(f"package.json is geen dict maar {type(package_data)}")
                        return
                    dependencies = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
                    for db_type, db_markers in DB_MARKERS.items():
                        for driver in db_markers.get("drivers", []):
                            if driver in dependencies:
                                detected_dbs.add(db_type)
                                logger.info(f"Database gedetecteerd via Node.js dependency: {db_type}")
            except json.JSONDecodeError as e:
                logger.warning(f"Kon package.json niet parsen als JSON: {e}")
            except Exception as e:
                logger.warning(f"Kon package.json niet lezen: {e}")
    
    elif app_type == "python":
        requirements_path = path / "requirements.txt"
        if requirements_path.exists():
            try:
                with open(requirements_path, 'r', encoding='utf-8') as f:
                    requirements = f.read().lower()
                    for db_type, db_markers in DB_MARKERS.items():
                        for driver in db_markers.get("drivers", []):
                            # Simpel: check of driver naam in requirements voorkomt
                            driver_lower = driver.lower()
                            if driver_lower in requirements:
                                detected_dbs.add(db_type)
                                logger.info(f"Database gedetecteerd via Python dependency: {db_type} (driver: {driver_lower})")
                                break  # Stop na eerste match voor deze database
            except Exception as e:
                logger.warning(f"Kon requirements.txt niet lezen: {e}")
    
    elif app_type == "php":
        composer_json_path = path / "composer.json"
        if composer_json_path.exists():
            try:
                with open(composer_json_path, 'r', encoding='utf-8') as f:
                    composer_data = json.load(f)
                    require = {**composer_data.get("require", {}), **composer_data.get("require-dev", {})}
                    for db_type, db_markers in DB_MARKERS.items():
                        for driver in db_markers.get("drivers", []):
                            # Check exact match of substring in package names
                            for pkg_name in require.keys():
                                if driver.lower() in pkg_name.lower():
                                    detected_dbs.add(db_type)
                                    logger.info(f"Database gedetecteerd via PHP dependency: {db_type} (via {pkg_name})")
                                    break
            except json.JSONDecodeError as e:
                logger.warning(f"Kon composer.json niet parsen als JSON: {e}")
            except Exception as e:
                logger.warning(f"Kon composer.json niet lezen: {e}")
    
    # Voeg database containers toe
    for db_type in detected_dbs:
        results["detected_databases"].append(db_type)
        db_image = _get_database_image(db_type)
        if db_image:
            results["containers"]["db"].append({
                "type": db_type,
                "image": db_image,
                "reason": f"Database gedetecteerd: {db_type}"
            })


def _get_runtime_image(app_type: str, runtime: str) -> str:
    """Geef Docker image voor runtime."""
    images = {
        "node": "node:20-alpine",
        "python": "python:3.11-slim"
    }
    return images.get(runtime, f"{runtime}:latest")


def _get_web_server_image(web_server: str) -> str:
    """Geef Docker image voor web server."""
    images = {
        "nginx": "nginx:alpine",
        "apache": "httpd:alpine"
    }
    return images.get(web_server, f"{web_server}:latest")


def _get_database_image(db_type: str) -> str:
    """Geef Docker image voor database."""
    images = {
        "mysql": "mysql:8.0",
        "postgresql": "postgres:16-alpine",
        "influxdb": "influxdb:2.7-alpine"
    }
    return images.get(db_type)


def detect_application_type(source_path: str) -> Dict:
    """
    Detecteer applicatietype en benodigde containers op basis van lokale directory.
    
    Args:
        source_path: Pad naar lokale directory (al opgehaald door collega)
    
    Returns:
        Dict met detectieresultaten met altijd: app_type, containers (web, api, db), 
        detected_files, detected_frameworks, detected_databases, confidence
        Of {"error": "..."} bij fouten
    """
    if not source_path:
        logger.error("source_path is verplicht maar niet opgegeven")
        return {
            "error": "source_path is verplicht",
            "app_type": "unknown",
            "containers": {"web": [], "api": [], "db": []},
            "detected_files": [],
            "detected_frameworks": [],
            "detected_databases": [],
            "confidence": 0
        }
    
    try:
        logger.info(f"Analyseren van directory: {source_path}")
        results = _analyze_directory(source_path)
        
        # Als er een error is, return die
        if "error" in results:
            logger.error(f"Fout bij analyse: {results['error']}")
            return results
        
        # Zorg dat containers altijd de juiste structuur hebben
        if "containers" not in results:
            results["containers"] = {"web": [], "api": [], "db": []}
        else:
            # Zorg dat alle drie de categorieën bestaan
            for category in ["web", "api", "db"]:
                if category not in results["containers"]:
                    results["containers"][category] = []
        
        # Log resultaten
        logger.info(f"Detectie voltooid:")
        logger.info(f"  - Applicatietype: {results.get('app_type', 'unknown')}")
        logger.info(f"  - Confidence: {results.get('confidence', 0):.1f}%")
        logger.info(f"  - Web containers: {len(results['containers']['web'])}")
        logger.info(f"  - API containers: {len(results['containers']['api'])}")
        logger.info(f"  - DB containers: {len(results['containers']['db'])}")
        
        return results
        
    except Exception as e:
        logger.error(f"Fout bij detectie: {e}", exc_info=True)
        return {
            "error": str(e),
            "app_type": "unknown",
            "containers": {"web": [], "api": [], "db": []},
            "detected_files": [],
            "detected_frameworks": [],
            "detected_databases": [],
            "confidence": 0
        }

