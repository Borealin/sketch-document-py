import json
from contextlib import contextmanager
import requests
import shutil
import tempfile
from dataclasses import dataclass
from os import path
from typing import Dict, Tuple, Any, Iterator


@dataclass
class Dist:
    shasum: str
    tarball: str


@dataclass
class VersionInfo:
    name: str
    version: str
    dist: Dist


@dataclass
class Package:
    name: str
    dist_tags: Dict[str, str]
    versions: Dict[str, VersionInfo]


def fetch_package_from_registry(package_name: str, registry: str) -> Package:
    url = f"{registry}/{package_name}"
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(f"{response.status_code} {response.reason}")
    response_json = response.json()
    return Package(
        name=response_json['name'],
        dist_tags=response_json['dist-tags'],
        versions={
            version: VersionInfo(
                name=version,
                version=version,
                dist=Dist(
                    shasum=package['dist']['shasum'],
                    tarball=package['dist']['tarball']
                )
            )
            for version, package in response_json['versions'].items()
        }
    )


@contextmanager
def get_package_tarball(package: Package, version: str) -> Iterator[str]:
    parsed_version = package.dist_tags[version] if version in package.dist_tags else version
    tarball_url = package.versions[parsed_version].dist.tarball
    temp_dir = tempfile.mkdtemp()
    try:
        tarball_file = path.join(temp_dir, path.basename(tarball_url))
        with requests.get(tarball_url) as response:
            with open(tarball_file, "wb") as f:
                f.write(response.content)
                tarball_dir = path.join(temp_dir, 'package')
                shutil.unpack_archive(
                    filename=tarball_file, extract_dir=temp_dir
                )
                yield tarball_dir
    finally:
        shutil.rmtree(temp_dir)


@dataclass
class Schemas:
    version: int
    versions: Tuple[int, ...]
    document: Dict[str, Any]
    fileFormat: Dict[str, Any]
    meta: Dict[str, Any]
    page: Dict[str, Any]
    user: Dict[str, Any]


def get_schemas(version: str) -> Schemas:
    package = fetch_package_from_registry('@sketch-hq/sketch-file-format', 'https://registry.npmjs.org/')
    with get_package_tarball(package, version) as tarball:
        def require(name):
            with open(path.join(tarball, 'dist', name)) as f:
                return json.load(f)

        file_format_schema_json = require('./file-format.schema.json')
        doc_schema_json = require('./document.schema.json')
        meta_schema_json = require('./meta.schema.json')
        page_schema_json = require('./page.schema.json')
        user_schema_json = require('./user.schema.json')
        versions = meta_schema_json.get('properties').get('version').get('enum')
        if versions is None:
            versions = ()
        return Schemas(
            version=0 if len(versions) == 0 else versions[-1],
            versions=versions,
            document=doc_schema_json,
            fileFormat=file_format_schema_json,
            meta=meta_schema_json,
            page=page_schema_json,
            user=user_schema_json
        )


__all__ = ['get_schemas', 'Schemas']
