import pytest

from pydicom.sr._cid_dict import (
    cid_concepts as CID_CONCEPTS,
    name_for_cid,
)
from pydicom.sr._concepts_dict import concepts as CONCEPTS
from pydicom.sr.coding import Code
from pydicom.sr.codedict import (
    codes,
    _CID_Dict,
    _CodesDict,
    ConceptCollection,
    AvailableCollections,
)


@pytest.fixture()
def ambiguous_scheme():
    """Add a scheme to the CID concepts dict that contains a duplicate attr"""
    cid = 6129
    attr = CID_CONCEPTS[cid]["SCT"][0]
    assert "FOO" not in CID_CONCEPTS[cid]
    CID_CONCEPTS[cid]["FOO"] = [attr]
    yield attr, cid
    del CID_CONCEPTS[cid]["FOO"]


@pytest.fixture()
def add_nonunique():
    """Add a non-unique keyword to the concepts dict"""
    CONCEPTS["TEST"] = {
        "Foo": {"BAR": ("Test A", [99999999999]), "BAZ": ("Test B", [99999999999])}
    }
    yield
    del CONCEPTS["TEST"]


@pytest.fixture()
def add_nonunique_cid():
    """Add a non-unique keyword to the CIDs dict"""
    CONCEPTS["TEST"] = {
        "Foo": {"BAR": ("Test A", [99999999999]), "BAZ": ("Test B", [99999999999])}
    }
    CID_CONCEPTS[99999999999] = {"TEST": ["Foo", "Foo"]}  # , "TEST2": ["Foo"]}
    name_for_cid[99999999999] = "Test"
    yield
    del CONCEPTS["TEST"]
    del CID_CONCEPTS[99999999999]
    del name_for_cid[99999999999]


class TestCode:
    def setup_method(self):
        self._value = "373098007"
        self._meaning = "Mean Value of population"
        self._scheme_designator = "SCT"

    def test_construction_kwargs(self):
        c = Code(
            value=self._value,
            scheme_designator=self._scheme_designator,
            meaning=self._meaning,
        )
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version is None

    def test_use_as_dictionary_key(self):
        c = Code(
            value=self._value,
            scheme_designator=self._scheme_designator,
            meaning=self._meaning,
        )
        d = {c: 1}
        assert c in d.keys()

    def test_construction_kwargs_optional(self):
        version = "v1.0"
        c = Code(
            value=self._value,
            scheme_designator=self._scheme_designator,
            meaning=self._meaning,
            scheme_version=version,
        )
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version == version

    def test_construction_args(self):
        c = Code(self._value, self._scheme_designator, self._meaning)
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version is None

    def test_construction_args_optional(self):
        version = "v1.0"
        c = Code(self._value, self._scheme_designator, self._meaning, version)
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version == version

    def test_equal(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code(self._value, self._scheme_designator, self._meaning)
        assert c1 == c2

    def test_not_equal(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code("373099004", "SCT", "Median Value of population")
        assert c1 != c2

    def test_equal_ignore_meaning(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code(self._value, self._scheme_designator, "bla bla bla")
        assert c1 == c2

    def test_equal_equivalent_coding(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code("R-00317", "SRT", self._meaning)
        assert c1 == c2
        assert c2 == c1

    def test_equal_not_in_snomed_mapping(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code("bla bal bla", "SRT", self._meaning)
        assert c1 != c2
        assert c2 != c1


class TestCodesDict:
    def test_dcm_1(self):
        assert codes.DCM.Modality == Code(
            value="121139", scheme_designator="DCM", meaning="Modality"
        )

    def test_dcm_2(self):
        assert codes.DCM.ProcedureReported == Code(
            value="121058",
            scheme_designator="DCM",
            meaning="Procedure Reported",
        )

    def test_dcm_3(self):
        assert codes.DCM.ImagingStartDatetime == Code(
            value="122712",
            scheme_designator="DCM",
            meaning="Imaging Start DateTime",
        )

    def test_sct_1(self):
        assert codes.SCT._1SigmaLowerValueOfPopulation == Code(
            value="371919006",
            scheme_designator="SCT",
            meaning="1 Sigma Lower Value of Populuation",
        )

    def test_sct_2(self):
        assert codes.SCT.FindingSite == Code(
            value="363698007", scheme_designator="SCT", meaning="Finding Site"
        )

    def test_cid250(self):
        assert codes.cid250.Positive == Code(
            value="10828004", scheme_designator="SCT", meaning="Positive"
        )

    def test_cid300(self):
        assert codes.cid300.NickelCobaltChromium == Code(
            value="261249004",
            scheme_designator="SCT",
            meaning="Nickel cobalt chromium",
        )

    def test_cid301(self):
        assert codes.cid301.MilligramsPerCubicCentimeter == Code(
            value="mg/cm3", scheme_designator="UCUM", meaning="mg/cm^3"
        )

    def test_cid402(self):
        assert codes.cid402.DestinationRoleID == Code(
            value="110152",
            scheme_designator="DCM",
            meaning="Destination Role ID",
        )

    def test_cid405(self):
        assert codes.cid405.MultiMediaCard == Code(
            value="110035", scheme_designator="DCM", meaning="Multi-media Card"
        )

    def test_cid610(self):
        assert codes.cid610.ReverseOsmosisPurifiedHclAcidifiedWater == Code(
            value="127291",
            scheme_designator="DCM",
            meaning="Reverse osmosis purified, HCl acidified water",
        )

    def test_cid612(self):
        assert codes.cid612.MonitoredAnesthesiaCareMAC == Code(
            value="398239001",
            scheme_designator="SCT",
            meaning="Monitored Anesthesia Care (MAC)",
        )

    def test_cid622(self):
        assert codes.cid622.NeuromuscularBlockingNMBNonDepolarizing == Code(
            value="372790002",
            scheme_designator="SCT",
            meaning="NeuroMuscular Blocking (NMB) - non depolarizing",
        )

    def test_cid630(self):
        assert codes.cid630.LidocainePrilocaine == Code(
            value="346553009",
            scheme_designator="SCT",
            meaning="Lidocaine + Prilocaine",
        )

    def test_cid643(self):
        assert codes.cid643._6Hydroxydopamine == Code(
            value="4624",
            scheme_designator="PUBCHEM_CID",
            meaning="6-Hydroxydopamine",
        )

    def test_cid646(self):
        assert codes.cid646.SPECTCTOfWholeBody == Code(
            value="127902",
            scheme_designator="DCM",
            meaning="SPECT CT of Whole Body",
        )

    def test_cid1003(self):
        assert codes.cid1003.LevelOfT11T12IntervertebralDisc == Code(
            value="243918001",
            scheme_designator="SCT",
            meaning="Level of T11/T12 intervertebral disc",
        )

    def test_cid3000(self):
        assert codes.cid3000.OperatorNarrative == Code(
            value="109111",
            scheme_designator="DCM",
            meaning="Operator's Narrative",
        )

    def test_cid3001_1(self):
        assert codes.cid3001.Avr == Code(
            value="2:65", scheme_designator="MDC", meaning="-aVR"
        )

    def test_cid3001_2(self):
        assert codes.cid3001.NegativeLowRightScapulaLead == Code(
            value="2:124",
            scheme_designator="MDC",
            meaning="negative: low right scapula Lead",
        )

    def test_cid3107(self):
        assert codes.cid3107._13Nitrogen == Code(
            value="21576001", scheme_designator="SCT", meaning="^13^Nitrogen"
        )

    def test_cid3111(self):
        assert codes.cid3111.Tc99mTetrofosmin == Code(
            value="424118002",
            scheme_designator="SCT",
            meaning="Tc-99m tetrofosmin",
        )

    def test_cid3263(self):
        meaning = "12-lead from EASI leads (ES, AS, AI) by Dower/EASI transformation"
        assert (
            codes.cid3263._12LeadFromEASILeadsESASAIByDowerEASITransformation
            == Code(
                value="10:11284",
                scheme_designator="MDC",
                meaning=meaning,
            )
        )

    def test_cid3335(self):
        assert codes.cid3335.PWaveSecondDeflectionInPWave == Code(
            value="10:320",
            scheme_designator="MDC",
            meaning="P' wave (second deflection in P wave)",
        )

    def test_contained(self):
        c = Code("24028007", "SCT", "Right")
        assert c in codes.cid244

    def test_not_contained(self):
        c = Code("130290", "DCM", "Median")
        assert c not in codes.cid244

    def test_dunder_dir(self):
        d = _CodesDict("UCUM")
        assert "ArbitraryUnit" in dir(d)
        assert "Year" in dir(d)
        assert "__delattr__" in dir(d)
        assert "trait_names" in dir(d)
        assert isinstance(dir(d), list)

    def test_dir(self):
        d = _CodesDict("UCUM")
        assert isinstance(d.dir(), list)
        assert "ArbitraryUnit" in d.dir()
        assert "Year" in d.dir()
        assert d.dir("xyz") == []
        assert "Radian" in d.dir("ia")

    def test_schemes(self):
        d = _CodesDict("UCUM")
        assert "UCUM" in list(d.schemes())
        schemes = list(codes.schemes())
        assert "UCUM" in schemes
        assert "DCM" in schemes
        assert "SCT" in schemes

    def test_trait_names(self):
        d = _CodesDict("UCUM")
        assert "ArbitraryUnit" in d.trait_names()
        assert "Year" in d.trait_names()
        assert "__delattr__" in d.trait_names()
        assert "trait_names" in d.trait_names()

    def test_getattr_CID_with_scheme_raises(self):
        msg = "Cannot use a CID with a scheme dictionary"
        with pytest.raises(AttributeError, match=msg):
            _CodesDict("UCUM").cid2

    def test_getattr_unknown_attr_raises(self):
        msg = "Unknown code name 'bar' for scheme 'UCUM'"
        with pytest.raises(AttributeError, match=msg):
            _CodesDict("UCUM").bar

    def test_getattr_nonunique_attr_raises(self, add_nonunique):
        msg = "Multiple code values for 'Foo' found: BAR, BAZ"
        with pytest.raises(RuntimeError, match=msg):
            _CodesDict("TEST").Foo


class TestCIDDict:
    def test_concepts(self):
        d = _CID_Dict(2)
        assert "Afferent" in d.concepts
        code = d.concepts["Afferent"]
        assert isinstance(code, Code)
        assert code.value == "49530007"

    def test_dunder_dir(self):
        d = _CID_Dict(2)
        assert "Afferent" in dir(d)
        assert "Vertical" in dir(d)
        assert "__contains__" in dir(d)
        assert "trait_names" in dir(d)
        assert isinstance(dir(d), list)

    def test_dir(self):
        d = _CID_Dict(2)
        assert isinstance(d.dir(), list)
        assert "Afferent" in d.dir()
        assert "Vertical" in d.dir()

        assert d.dir("xyz") == []
        assert "Axial" in d.dir("ia")
        assert "Superficial" in d.dir("ia")
        assert "Axial" in d.dir("IA")
        assert "Superficial" in d.dir("IA")

    def test_trait_names(self):
        d = _CID_Dict(2)
        assert isinstance(d.trait_names(), list)
        assert "Afferent" in d.trait_names()
        assert "Vertical" in d.trait_names()

    def test_str(self):
        d = _CID_Dict(2)
        s = str(d)
        assert "CID 2 (AnatomicModifier)" in s
        assert "Afferent             49530007     SCT      Afferent" in s
        assert "Vertical             33096000     SCT      Vertical" in s

    def test_repr(self):
        d = _CID_Dict(2)
        r = repr(d)
        assert "CID 2" in r
        assert "Afferent = Code(value='49530007'" in r
        assert "Vertical = Code(value='33096000'" in r

    def test_getattr_match(self):
        d = _CID_Dict(2)
        code = d.Afferent
        assert isinstance(code, Code)
        assert code.value == "49530007"

    def test_getattr_no_match_raises(self):
        d = _CID_Dict(2)
        msg = r"'XYZ' not found in CID 2"
        with pytest.raises(AttributeError, match=msg):
            d.XYZ

    def test_getattr_match_multiple_codes_raises(self, add_nonunique_cid):
        # Same attribute for multiple codes
        d = _CID_Dict(99999999999)
        msg = r"'Foo' has multiple code matches in CID 99999999999: 'BAR', 'BAZ'"
        with pytest.raises(AttributeError, match=msg):
            d.Foo

    def test_getattr_ambiguous_attr_raises(self, ambiguous_scheme):
        attr, cid = ambiguous_scheme
        msg = f"Multiple schemes found for '{attr}' in CID 6129: SCT, FOO"
        with pytest.raises(AttributeError, match=msg):
            getattr(_CID_Dict(cid), attr)


class TestConceptCollection:
    """Tests for ConceptCollection"""

    def test_init(self):
        """Test creation of new collections"""
        coll = ConceptCollection("SCT")
        assert coll.name == "SCT"
        assert coll.scheme_designator == "SCT"
        assert coll.is_cid is False

        coll = ConceptCollection("CID2")
        assert coll.name == "CID2"
        assert coll.scheme_designator == "CID2"
        assert coll.is_cid is True

    def test_concepts(self):
        """Test ConceptCollection.concepts"""
        coll = ConceptCollection("UCUM")
        assert coll._concepts == {}
        concepts = coll.concepts
        assert coll._concepts != {}
        assert concepts["Second"] == Code(
            "s", scheme_designator="UCUM", meaning="second"
        )

        coll = ConceptCollection("CID2")
        assert coll.concepts["Transverse"] == Code(
            "62824007", scheme_designator="SCT", meaning="Transverse"
        )

    def test_contains(self):
        """Test the in operator"""
        coll = ConceptCollection("UCUM")
        assert "Second" in coll
        assert "Foo" not in coll

        coll = ConceptCollection("CID2")
        assert "Transverse" in coll
        assert "Foo" not in coll

    def test_dir(self):
        """Test dir()"""
        coll = ConceptCollection("UCUM")
        assert "Second" in dir(coll)
        assert "Foo" not in dir(coll)

        coll = ConceptCollection("CID2")
        assert "Transverse" in dir(coll)
        assert "Foo" not in dir(coll)

        # Check None_
        coll = ConceptCollection("CID606")
        assert "None_" in coll
        assert "None_" in dir(coll)

        # Check _125Iodine
        coll = ConceptCollection("CID18")
        assert "_125Iodine" in coll
        assert "_125Iodine" in dir(coll)

    def test_getattr(self):
        """Test ConceptCollection.Foo"""
        coll = ConceptCollection("UCUM")
        assert coll.Second == Code("s", scheme_designator="UCUM", meaning="second")
        msg = "No matching code for keyword 'Foo' in scheme 'UCUM'"
        with pytest.raises(AttributeError, match=msg):
            coll.Foo

        coll = ConceptCollection("CID2")
        assert coll.Transverse == Code(
            "62824007", scheme_designator="SCT", meaning="Transverse"
        )

        msg = "No matching code for keyword 'Foo' in CID2"
        with pytest.raises(AttributeError, match=msg):
            coll.Foo

        coll.foo = None
        assert coll.foo is None

    def test_getattr_multiple_raises(self, add_nonunique):
        """Test non-unique results for the keyword"""
        coll = ConceptCollection("TEST")
        msg = "Multiple codes found for keyword 'Foo' in scheme 'TEST': BAR, BAZ"
        with pytest.raises(RuntimeError, match=msg):
            coll.Foo

    def test_getattr_multiple_raises_cid(self, add_nonunique_cid):
        """Test non-unique results for the keyword"""
        coll = ConceptCollection("CID99999999999")
        msg = "Multiple codes found for keyword 'Foo' in CID99999999999: BAR, BAZ"
        with pytest.raises(RuntimeError, match=msg):
            coll.Foo

        coll._cid_data["TEST2"] = ["Foo"]
        msg = (
            "Multiple schemes found to contain the keyword 'Foo' in CID99999999999: "
            "TEST, TEST2"
        )
        with pytest.raises(RuntimeError, match=msg):
            coll.Foo

    def test_repr(self):
        """Test repr()"""
        coll = ConceptCollection("UCUM")
        assert (
            "Second = Code(value='s', scheme_designator='UCUM', meaning='second', "
            "scheme_version=None)"
        ) in repr(coll)

        coll = ConceptCollection("CID2")
        assert (
            "Transverse = Code(value='62824007', scheme_designator='SCT', "
            "meaning='Transverse', scheme_version=None)"
        ) in repr(coll)

    def test_str(self):
        """Test str()"""
        coll = ConceptCollection("UCUM")
        assert (
            "Second                                                  s          "
            "                  second\n"
        ) in str(coll)

        coll = ConceptCollection("CID2")
        assert "Transverse       62824007    SCT      Transverse\n" in str(coll)

    def test_trait_names(self):
        """Test trait_names()"""
        traits = ConceptCollection("UCUM").trait_names()
        assert "Second" in traits
        assert "Foo" not in traits

        traits = ConceptCollection("CID2").trait_names()
        assert "Transverse" in traits
        assert "Foo" not in traits


class TestAvailableCollections:
    """Tests for AvailableCollections"""

    def test_init(self):
        """Test creating a new instance"""
        colls = AvailableCollections(
            [ConceptCollection("SCT"), ConceptCollection("CID2")]
        )

        assert list(colls.collections) == ["SCT", "CID2"]
        assert colls.schemes() == ["SCT"]
        assert colls.CIDs() == ["CID2"]

    def test_getattr(self):
        """Test AvailableCollections.Foo"""
        colls = AvailableCollections(
            [ConceptCollection("SCT"), ConceptCollection("CID2")]
        )

        assert isinstance(colls.SCT, ConceptCollection)
        assert isinstance(colls.CID2, ConceptCollection)

        colls.foo = None
        assert colls.foo is None
