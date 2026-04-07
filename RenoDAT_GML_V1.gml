<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:app="http://www.opengis.net/citygml/appearance/2.0" xmlns:bldg="http://www.opengis.net/citygml/building/2.0" xmlns:brid="http://www.opengis.net/citygml/bridge/2.0" xmlns:core="http://www.opengis.net/citygml/2.0" xmlns:dem="http://www.opengis.net/citygml/relief/2.0" xmlns:frn="http://www.opengis.net/citygml/cityfurniture/2.0" xmlns:gen="http://www.opengis.net/citygml/generics/2.0" xmlns:gml="http://www.opengis.net/gml" xmlns:grp="http://www.opengis.net/citygml/cityobjectgroup/2.0" xmlns:luse="http://www.opengis.net/citygml/landuse/2.0" xmlns:nrg3="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0" xmlns:pbase="http://www.opengis.net/citygml/profiles/base/2.0" xmlns:sch="http://www.ascc.net/xml/schematron" xmlns:smil20="http://www.w3.org/2001/SMIL20/" xmlns:smil20lang="http://www.w3.org/2001/SMIL20/Language" xmlns:tex="http://www.opengis.net/citygml/texturedsurface/2.0" xmlns:tran="http://www.opengis.net/citygml/transportation/2.0" xmlns:tun="http://www.opengis.net/citygml/tunnel/2.0" xmlns:veg="http://www.opengis.net/citygml/vegetation/2.0" xmlns:wtr="http://www.opengis.net/citygml/waterbody/2.0" xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
	<gml:description>This is a description</gml:description>
	<gml:name>RenoDAT City</gml:name>
	<core:cityObjectMember>
		<bldg:Building gml:id="id_building_1">
			<gml:name>Han solo's house</gml:name>
			<core:creationDate>2026-04-04</core:creationDate>
			<nrg3:device>
				<nrg3:PhotovoltaicCollector gml:id="pv_panel_1">
					<gml:name>PV collector (36x270 Wp)</gml:name>
					<core:creationDate>2026-04-04</core:creationDate>
					<nrg3:model>PV-16-270 PW</nrg3:model>
					<nrg3:yearOfInstallation>2020</nrg3:yearOfInstallation>
					<nrg3:numberOfDevices>36</nrg3:numberOfDevices>
					<nrg3:installedPower uom="W">9720</nrg3:installedPower>
					<nrg3:azimuth uom="deg">235.65</nrg3:azimuth>
					<nrg3:inclination uom="deg">44.51</nrg3:inclination>
					<nrg3:cellType>unknown</nrg3:cellType>
				</nrg3:PhotovoltaicCollector>
			</nrg3:device>
			<nrg3:identifier codeSpace="https://bagviewer.kadaster.nl/?objectId=0503100000032914">0503100000032914</nrg3:identifier>
			<nrg3:metadata>
				<nrg3:Metadata>
					<nrg3:author>Daan Schlosser</nrg3:author>
					<nrg3:acquisitionMethod>measurement</nrg3:acquisitionMethod>
					<nrg3:owner>Han Solo</nrg3:owner>
				</nrg3:Metadata>
			</nrg3:metadata>
			<bldg:class codeSpace="http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_class.xml">1000</bldg:class>
			<bldg:function codeSpace="http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_function.xml">1000</bldg:function>
			<bldg:usage codeSpace="http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_usage.xml">1000</bldg:usage>
			<bldg:yearOfConstruction>2020</bldg:yearOfConstruction>
			<bldg:roofType codeSpace="https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_roofType.xml">1030</bldg:roofType>
			<bldg:storeysAboveGround>3</bldg:storeysAboveGround>
			<bldg:storeysBelowGround>0</bldg:storeysBelowGround>
			<nrg3:bdgIsProtected>false</nrg3:bdgIsProtected>
			<nrg3:bdgNumberOfBuildingUnits>1</nrg3:bdgNumberOfBuildingUnits>
			<nrg3:bdgOwnerName>Han Solo</nrg3:bdgOwnerName>
			<nrg3:bdgOwnershipType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/OwnershipTypeValue.xml">occupantPrivateOwner</nrg3:bdgOwnershipType>
			<nrg3:bdgType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/BuildingTypeValue.xml">singleFamilyHouse</nrg3:bdgType>
			<nrg3:bdgVolume>
				<nrg3:QualifiedVolume>
					<nrg3:description>Building's gross volume of 3D model</nrg3:description>
					<nrg3:source>3D model</nrg3:source>
					<nrg3:value uom="m3">823.30</nrg3:value>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/VolumeTypeValue.xml">grossVolume</nrg3:type>
				</nrg3:QualifiedVolume>
			</nrg3:bdgVolume>
		</bldg:Building>
	</core:cityObjectMember>
</core:CityModel>