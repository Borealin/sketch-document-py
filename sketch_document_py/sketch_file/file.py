# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from functools import reduce
from typing import Dict, List, Optional
from uuid import UUID

from sketch_document_py.sketch_file_format import Contents, ContentsDocument, Meta, Page, User, Workspace, FileRef


@dataclass
class SketchFile:
    filepath: str
    contents: Contents

    __do_objectID: Optional[str] = None

    @property
    def do_objectID(self) -> str:
        if self.__do_objectID is None:
            self.__do_objectID = UUID(
                int=reduce(lambda x, y: x ^ UUID(y.do_objectID).int, self.contents.document.pages, 0)).hex.upper()
        return self.__do_objectID


def from_file(file_path: str) -> SketchFile:
    """
    load SketchFile object from sketch file
    @param file_path: the sketch file path
    @return: the well-structured SketchFile dataclass object
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f'{file_path} not found')
    if not zipfile.is_zipfile(file_path):
        raise ValueError(f'{file_path} is not a zip file')
    zip_file = zipfile.ZipFile(file_path)
    document_dict = json.loads(zip_file.read('document.json'))
    if not (isinstance(document_dict, dict) and 'pages' in document_dict.keys()):
        raise ValueError(f'{file_path}/document.json is not valid')
    pages: List[Page] = []
    for page in document_dict['pages']:
        if not (isinstance(page, dict) and '_ref' in page.keys()):
            raise ValueError(f'{file_path}/document.json is not valid')
        page_dict = json.loads(zip_file.read(f"{page['_ref']}.json"))
        pages.append(page_dict)
    document_dict['pages'] = pages
    document: ContentsDocument = ContentsDocument.from_dict(document_dict)
    workspace: Workspace = {str(Path(os.path.basename(file)).with_suffix('')): json.loads(zip_file.read(file)) for file in
                            filter(
                                lambda x: x.startswith('workspace/') and x.endswith('.json'),
                                zip_file.namelist())}
    meta = Meta.from_dict(json.loads(zip_file.read('meta.json')))
    user: User = json.loads(zip_file.read('user.json'))
    return SketchFile(file_path, Contents(document, meta, user, workspace))


def to_file(obj: SketchFile, alter_file_path: str = None, keep_static_file: bool = False):
    """
    save changed SketchFile object to sketch file
    @param keep_static_file: should keep embedded static file
    @param obj: SketchFile dataclass object
    @param alter_file_path: the new file_path
    """
    temp_dir = None
    backup_sketch_path = None
    if keep_static_file:
        temp_dir = tempfile.mkdtemp()
        backup_sketch_path = os.path.join(temp_dir, 'temp.sketch')
        if os.path.exists(obj.filepath):
            shutil.copy(obj.filepath, backup_sketch_path)
    file_path = obj.filepath if alter_file_path is None else alter_file_path
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        refs: List[Dict[str, str]] = []
        for page in obj.contents.document.pages:
            zip_file.writestr(
                os.path.join('pages', f'{page.do_objectID}.json'),
                json.dumps(page.to_dict(), ensure_ascii=False).encode('utf-8')
            )
            refs.append(FileRef(
                class_='MSJSONFileReference',
                ref=f'pages/{page.do_objectID}',
                ref_class='MSImmutablePage'
            ).to_dict())
        if obj.contents.workspace is not None:
            for (key, value) in obj.contents.workspace.items():
                zip_file.writestr(
                    os.path.join('workspace', f'{key}.json'),
                    json.dumps(value, ensure_ascii=False).encode('utf-8')
                )
        document_dict = obj.contents.document.to_dict()
        document_dict['pages'] = refs
        zip_file.writestr(
            'document.json',
            json.dumps(document_dict, ensure_ascii=False).encode('utf-8')
        )
        zip_file.writestr('user.json', json.dumps(
            obj.contents.user, ensure_ascii=False).encode('utf-8'))
        zip_file.writestr('meta.json', json.dumps(
            obj.contents.meta.to_dict(), ensure_ascii=False).encode('utf-8'))
        if keep_static_file and backup_sketch_path is not None:
            with zipfile.ZipFile(backup_sketch_path, 'r') as backup_sketch:
                for info in backup_sketch.infolist():
                    if info.filename not in [i.filename for i in zip_file.infolist()]:
                        zip_file.writestr(info, backup_sketch.read(info))
    if keep_static_file and temp_dir is not None:
        shutil.rmtree(temp_dir)


__all__ = [
    'from_file', 'to_file', 'SketchFile'
]

if __name__ == '__main__':
    sketch_file = from_file('/Users/bytedance/Desktop/test.sketch')
    for page in sketch_file.contents.document.pages:
        print(page.layers[0].to_json(indent=4))
