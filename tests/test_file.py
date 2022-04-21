import unittest
from os.path import abspath, dirname, join, exists
from os import remove
import sketch_document_py.sketch_file_format as file_format
from sketch_document_py.sketch_file import SketchFile, from_file, to_file

FILE_WITH_ASSISTANTS = join(dirname(abspath(__file__)), './with-assistants.sketch')
FILE_WITH_WORKSPACE_DATA = join(dirname(abspath(__file__)), './with-workspace-data.sketch')
FILE_WITH_COLOR_VARIABLES = join(dirname(abspath(__file__)), './with-color-variables.sketch')


class ToFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.OUTPUT = join(dirname(abspath(__file__)), './generated-file.sketch')
        blank_page = file_format.Page(
            class_='page',
            do_objectID='628bbfa8-404c-48d5-95b0-3316c1e39fb0',
            name='Blank Page',
            booleanOperation=file_format.BooleanOperation.None_,
            isFixedToViewport=False,
            isFlippedHorizontal=False,
            isFlippedVertical=False,
            isLocked=False,
            isVisible=True,
            layerListExpandedType=file_format.LayerListExpanded.Undecided,
            nameIsFixed=False,
            resizingConstraint=63,
            resizingType=file_format.ResizeType.Stretch,
            rotation=0,
            shouldBreakMaskChain=False,
            exportOptions=file_format.ExportOptions(
                class_='exportOptions',
                includedLayerIds=[],
                layerOptions=0,
                shouldTrim=False,
                exportFormats=[],
            ),
            frame=file_format.Rect(
                class_='rect',
                constrainProportions=True,
                height=0,
                width=0,
                x=0,
                y=0,
            ),
            clippingMaskMode=0,
            hasClippingMask=False,
            hasClickThrough=True,
            groupLayout=file_format.FreeformGroupLayout(class_='MSImmutableFreeformGroupLayout'),
            layers=[],
            horizontalRulerData=file_format.RulerData(class_='rulerData', base=0, guides=[]),
            verticalRulerData=file_format.RulerData(class_='rulerData', base=0, guides=[]),
        )
        contents = file_format.Contents(
            document=file_format.ContentsDocument(
                class_='document',
                assets=file_format.AssetCollection(
                    class_='assetCollection',
                    colorAssets=[],
                    colors=[],
                    do_objectID='0377C8BC-E3EC-40BF-A3D9-65812526D041',
                    exportPresets=[],
                    gradientAssets=[],
                    gradients=[],
                    images=[]
                ),
                colorSpace=file_format.ColorSpace.SRGB,
                currentPageIndex=0,
                do_objectID='d1ffdd39-4d43-41f7-9cab-b68c82c91c4e',
                foreignLayerStyles=[],
                foreignSymbols=[],
                foreignTextStyles=[],
                layerStyles=file_format.SharedStyleContainer(
                    class_='sharedStyleContainer',
                    objects=[],
                    do_objectID='88d3ce1e-b7af-4133-af56-088a193db726',
                ),
                layerTextStyles=file_format.SharedTextStyleContainer(
                    class_='sharedTextStyleContainer',
                    objects=[],
                    do_objectID='b08e8447-b31d-4901-abb7-8284e1f71113'
                ),
                pages=[blank_page],
            ),
            meta=file_format.Meta(
                app=file_format.BundleId.Testing,
                appVersion='72',
                commit='6896e2bfdb0a2a03f745e4054a8c5fc58565f9f1',
                pagesAndArtboards={},
                version=136,
                autosaved=file_format.NumericalBool.True_,
                build=0,
                compatibilityVersion=99,
                variant='TESTING',
                created=file_format.MetaCreated(
                    commit='6896e2bfdb0a2a03f745e4054a8c5fc58565f9f1',
                    appVersion='72',
                    build=0,
                    app=file_format.BundleId.Testing,
                    compatibilityVersion=99,
                    variant='TESTING',
                    version=136,
                ),
                saveHistory=[''],
            ),
            user=dict(
                document={
                    'pageListCollapsed': 0,
                    'pageListHeight': 100,
                    'expandedSymbolPathsInSidebar': [],
                    'expandedTextStylePathsInPopover': []
                },
            ),
            workspace={
                'one': 'string',
                'two': [1, 2, 3],
                'three': {
                    'a': True,
                    'b': ['foo', 'bar', 'baz']
                }
            }
        )
        self.file = SketchFile(filepath=self.OUTPUT, contents=contents)

    def test(self):
        to_file(self.file)
        assert exists(self.OUTPUT)

        file = from_file(self.OUTPUT)
        assert isinstance(file.contents.workspace, dict)
        assert len(file.contents.workspace.keys()) == 3
        assert file.contents.workspace['one'] == 'string'
        assert isinstance(file.contents.workspace['two'], list)
        assert file.contents.workspace['two'][1] == 2
        assert isinstance(file.contents.workspace['three'], dict)
        assert file.contents.workspace['three']['a']

    def tearDown(self) -> None:
        remove(self.OUTPUT)


class FromFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.file = from_file(FILE_WITH_COLOR_VARIABLES)

    def test_parses_document_entry(self):
        assert self.file.contents.document.class_ == 'document'

    def test_parse_document_pages_as_array_of_page_objects(self):
        assert self.file.contents.document.pages[0].class_ == 'page'
        assert len(self.file.contents.document.pages) == 2

    def test_parse_meta_entry(self):
        assert self.file.contents.meta.version == 136

    def test_parse_user_entry(self):
        assert self.file.contents.user['document']['pageListHeight'] == 87.5

    def test_parse_color_variables_correctly(self):
        assert len(self.file.contents.document.sharedSwatches.objects) == 3

    def test_parse_assistants_data(self):
        file = from_file(FILE_WITH_ASSISTANTS)
        assert len(file.contents.workspace['assistants']['dependencies']) == 2

    def test_parse_random_data_in_the_workspace_folder(self):
        file = from_file(FILE_WITH_WORKSPACE_DATA)
        assert isinstance(file.contents.workspace, dict)
        assert len(file.contents.workspace) == 3
        assert file.contents.workspace['fruit']['fruit'] == 'Apple'
        assert file.contents.workspace['quiz']['quiz']['maths']['q2']['options'][0] == '1'
