import os
import json
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Detectie markers voor verschillende applicatietypes
DETECTION_MARKERS = {
    "php": {
        "files": ["composer.json", "composer.lock"],
        "extensions": [".php"],
        "web_servers": ["apache", "nginx"],
        "runtime": "php-fpm",
        "db_drivers": ["pdo_mysql", "pdo_pgsql", "mysqli"]
    },
    "nodejs": {
        "files": ["package.json", "package-lock.json", "yarn.lock"],
        "extensions": [".js", ".jsx", ".ts", ".tsx"],
        "web_servers": ["nginx"],  # Voor statische assets
        "runtime": "node",
        "api_frameworks": ["express", "fastify", "koa", "nest"],
        "web_frameworks": ["next", "nuxt", "gatsby", "react", "vue"]
    },
    "python": {
        "files": ["requirements.txt", "setup.py", "pyproject.toml", "Pipfile", "poetry.lock"],
        "extensions": [".py"],
        "web_servers": ["nginx"],
        "runtime": "python",
        "api_frameworks": ["fastapi", "flask", "django", "tornado"],
        "db_drivers": ["psycopg2", "mysql-connector", "sqlalchemy"]
    },
    "java": {
        "files": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "extensions": [".java", ".jar"],
        "web_servers": ["tomcat", "jetty"],
        "runtime": "java",
        "api_frameworks": ["spring-boot", "spring", "quarkus"]
    },
    "go": {
        "files": ["go.mod", "go.sum"],
        "extensions": [".go"],
        "web_servers": ["nginx"],
        "runtime": "go",
        "api_frameworks": ["gin", "echo", "fiber"]
    },
    "ruby": {
        "files": ["Gemfile", "Gemfile.lock"],
        "extensions": [".rb"],
        "web_servers": ["nginx"],
        "runtime": "ruby",
        "api_frameworks": ["rails", "sinatra"]
    }
}

# Database detectie markers
DB_MARKERS = {
    "mysql": {
        "keywords": ["mysql", "mariadb"],
        "drivers": ["mysql-connector", "pymysql", "mysql2", "mysqli", "pdo_mysql"],
        "config_patterns": ["mysql://", "mariadb://"]
    },
    "postgresql": {
        "keywords": ["postgres", "postgresql", "pg"],
        "drivers": ["psycopg2", "pg", "postgres", "postgresql"],
        "config_patterns": ["postgres://", "postgresql://"]
    },
    "mongodb": {
        "keywords": ["mongodb", "mongo"],
        "drivers": ["pymongo", "mongoose", "mongodb"],
        "config_patterns": ["mongodb://"]
    },
    "redis": {
        "keywords": ["redis"],
        "drivers": ["redis", "ioredis", "redis-py"],
        "config_patterns": ["redis://"]
    },
    "influxdb": {
        "keywords": ["influxdb", "influx"],
        "drivers": ["influxdb-client", "influx"],
        "config_patterns": ["influxdb://"]
    },
    "sqlite": {
        "keywords": ["sqlite"],
        "drivers": ["sqlite3", "sqlite"],
        "config_patterns": [".db", ".sqlite"]
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

    # Detecteer applicatietype
    for app_type, markers in DETECTION_MARKERS.items():
        score = 0
        found_files = []
        
        # Check voor marker bestanden
        for marker_file in markers.get("files", []):
            if marker_file in all_files or any(f.endswith(marker_file) for f in all_files):
                score += 10
                found_files.append(marker_file)
        
        # Check voor bestandsextensies
        extension_count = sum(1 for f in all_files if any(f.endswith(ext) for ext in markers.get("extensions", [])))
        if extension_count > 0:
            score += min(extension_count / 10, 5)  # Max 5 punten
        
        if score > 0:
            detected_types.append({
                "type": app_type,
                "score": score,
                "found_files": found_files
            })
            results["detected_files"].extend(found_files)

    # Selecteer het meest waarschijnlijke type
    if detected_types:
        best_match = max(detected_types, key=lambda x: x["score"])
        results["app_type"] = best_match["type"]
        results["confidence"] = min(best_match["score"] / 15 * 100, 100)
        logger.info(f"Gedetecteerd applicatietype: {results['app_type']} (confidence: {results['confidence']:.1f}%)")

    # Analyseer configuratiebestanden voor frameworks en databases
    if results["app_type"] != "unknown":
        markers = DETECTION_MARKERS[results["app_type"]]
        
        # Check voor API frameworks
        if results["app_type"] == "nodejs":
            _detect_nodejs_frameworks(path, results, markers)
        elif results["app_type"] == "python":
            _detect_python_frameworks(path, results, markers)
        
        # Voeg runtime containers toe
        runtime = markers.get("runtime")
        if runtime:
            if results["app_type"] in ["nodejs", "python", "go", "ruby"]:
                results["containers"]["api"].append({
                    "type": runtime,
                    "image": _get_runtime_image(results["app_type"], runtime),
                    "reason": f"Runtime voor {results['app_type']} applicatie"
                })
            elif results["app_type"] == "php":
                results["containers"]["web"].append({
                    "type": runtime,
                    "image": "php:8-fpm",
                    "reason": "PHP-FPM runtime"
                })
        
        # Voeg web servers toe
        for web_server in markers.get("web_servers", []):
            results["containers"]["web"].append({
                "type": web_server,
                "image": _get_web_server_image(web_server),
                "reason": f"Web server voor {results['app_type']} applicatie"
            })

    # Detecteer databases
    _detect_databases(path, all_files, results)

    return results


def _detect_nodejs_frameworks(path: Path, results: Dict, markers: Dict):
    """Detecteer Node.js frameworks."""
    package_json_path = path / "package.json"
    if package_json_path.exists():
        try:
            with open(package_json_path, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
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
    """Detecteer gebruikte databases."""
    detected_dbs = set()
    
    # Check configuratiebestanden
    config_files = [".env", ".env.local", "config.json", "config.yml", "config.yaml", 
                   "application.properties", "application.yml", "settings.py", "config.php"]
    
    for config_file in config_files:
        config_path = path / config_file
        if config_path.exists():
            try:
                content = config_path.read_text(encoding='utf-8', errors='ignore').lower()
                for db_type, db_markers in DB_MARKERS.items():
                    for pattern in db_markers.get("config_patterns", []):
                        if pattern in content:
                            detected_dbs.add(db_type)
                            logger.info(f"Database gedetecteerd via config: {db_type}")
            except Exception as e:
                logger.warning(f"Kon config bestand niet lezen: {e}")
    
    # Check dependencies
    if results["app_type"] == "nodejs":
        package_json_path = path / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r', encoding='utf-8') as f:
                    package_data = json.load(f)
                    dependencies = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
                    for db_type, db_markers in DB_MARKERS.items():
                        for driver in db_markers.get("drivers", []):
                            if driver in dependencies:
                                detected_dbs.add(db_type)
                                logger.info(f"Database gedetecteerd via dependency: {db_type}")
            except Exception as e:
                logger.warning(f"Kon package.json niet lezen: {e}")
    
    elif results["app_type"] == "python":
        requirements_path = path / "requirements.txt"
        if requirements_path.exists():
            try:
                with open(requirements_path, 'r', encoding='utf-8') as f:
                    requirements = f.read().lower()
                    for db_type, db_markers in DB_MARKERS.items():
                        for driver in db_markers.get("drivers", []):
                            if driver in requirements:
                                detected_dbs.add(db_type)
                                logger.info(f"Database gedetecteerd via dependency: {db_type}")
            except Exception as e:
                logger.warning(f"Kon requirements.txt niet lezen: {e}")
    
    # Voeg database containers toe
    for db_type in detected_dbs:
        results["detected_databases"].append(db_type)
        results["containers"]["db"].append({
            "type": db_type,
            "image": _get_database_image(db_type),
            "reason": f"Database gedetecteerd: {db_type}"
        })


def _get_runtime_image(app_type: str, runtime: str) -> str:
    """Geef Docker image voor runtime."""
    images = {
        "node": "node:20-alpine",
        "python": "python:3.11-slim",
        "go": "golang:1.21-alpine",
        "ruby": "ruby:3.2-alpine"
    }
    return images.get(runtime, f"{runtime}:latest")


def _get_web_server_image(web_server: str) -> str:
    """Geef Docker image voor web server."""
    images = {
        "nginx": "nginx:alpine",
        "apache": "httpd:alpine",
        "tomcat": "tomcat:latest",
        "jetty": "jetty:latest"
    }
    return images.get(web_server, f"{web_server}:latest")


def _get_database_image(db_type: str) -> str:
    """Geef Docker image voor database."""
    images = {
        "mysql": "mysql:8.0",
        "postgresql": "postgres:16-alpine",
        "mongodb": "mongo:7",
        "redis": "redis:7-alpine",
        "influxdb": "influxdb:2.7-alpine",
        "sqlite": None  # SQLite heeft geen container nodig
    }
    return images.get(db_type, f"{db_type}:latest")


def detect_application_type(source_path: str) -> Dict:
    """
    Detecteer applicatietype en benodigde containers op basis van lokale directory.
    
    Args:
        source_path: Pad naar lokale directory (al opgehaald door collega)
    
    Returns:
        Dict met detectieresultaten
    """
    if not source_path:
        return {"error": "source_path is verplicht"}
    
    try:
        logger.info(f"Analyseren van directory: {source_path}")
        results = _analyze_directory(source_path)
        
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
        return {"error": str(e)}

