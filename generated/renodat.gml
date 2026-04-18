<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:app="http://www.opengis.net/citygml/appearance/2.0" xmlns:bldg="http://www.opengis.net/citygml/building/2.0" xmlns:brid="http://www.opengis.net/citygml/bridge/2.0" xmlns:core="http://www.opengis.net/citygml/2.0" xmlns:dem="http://www.opengis.net/citygml/relief/2.0" xmlns:frn="http://www.opengis.net/citygml/cityfurniture/2.0" xmlns:gen="http://www.opengis.net/citygml/generics/2.0" xmlns:gml="http://www.opengis.net/gml" xmlns:grp="http://www.opengis.net/citygml/cityobjectgroup/2.0" xmlns:luse="http://www.opengis.net/citygml/landuse/2.0" xmlns:nrg3="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0" xmlns:pbase="http://www.opengis.net/citygml/profiles/base/2.0" xmlns:sch="http://www.ascc.net/xml/schematron" xmlns:smil20="http://www.w3.org/2001/SMIL20/" xmlns:smil20lang="http://www.w3.org/2001/SMIL20/Language" xmlns:tex="http://www.opengis.net/citygml/texturedsurface/2.0" xmlns:tran="http://www.opengis.net/citygml/transportation/2.0" xmlns:tun="http://www.opengis.net/citygml/tunnel/2.0" xmlns:veg="http://www.opengis.net/citygml/vegetation/2.0" xmlns:wtr="http://www.opengis.net/citygml/waterbody/2.0" xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
	<gml:description xlink:type="simple">Example CityGML2.0 + EnergyADE3.0 dataset for a single-family residence with various energy-related features and metadata.</gml:description>
	<gml:name>RenoDAT City</gml:name>
	<gml:boundedBy>
		<gml:Envelope srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
			<gml:lowerCorner srsDimension="3">85182.94780530749 446868.4517295427 -0.38699999999994</gml:lowerCorner>
			<gml:upperCorner srsDimension="3">85200.91877905159 446886.4462633794 9.2511000000144</gml:upperCorner>
		</gml:Envelope>
	</gml:boundedBy>
	<core:cityObjectMember xlink:type="simple">
		<bldg:Building gml:id="id_building_1">
			<nrg3:Metadata xlink:type="simple">
				<nrg3:author>Daan Schlosser</nrg3:author>
				<nrg3:acquisitionMethod>measurement</nrg3:acquisitionMethod>
				<nrg3:owner>Han Solo</nrg3:owner>
				<nrg3:qualityDescription>Gross floor area disagrees between BAG register (122.0 m2) and the measured 3D model (119.6 m2); both values are retained as separate QualifiedArea entries so downstream tooling can pick the provenance it trusts.</nrg3:qualityDescription>
				<nrg3:source>BAG + RenoDAT measurement survey</nrg3:source>
			</nrg3:Metadata>
			<gml:name>Han Solo's House</gml:name>
			<core:creationDate>2026-04-04</core:creationDate>
			<nrg3:identifier codeSpace="https://example.invalid/bag">0000000000000001</nrg3:identifier>
			<nrg3:device xlink:type="simple">
				<nrg3:PhotovoltaicCollector gml:id="pv_panel_1">
					<gml:name>PV collector (36x270 Wp)</gml:name>
					<core:creationDate>2026-04-04</core:creationDate>
					<nrg3:resource xlink:type="simple">
						<nrg3:Energy gml:id="id_pv_production_1">
							<gml:description xlink:type="simple">PV energy production for pv_panel_1</gml:description>
							<gml:name>PV Production pv_panel_1</gml:name>
							<nrg3:creationDate>2026-04-04</nrg3:creationDate>
							<nrg3:operationType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ResourceOperationTypeValue.xml">produces</nrg3:operationType>
							<nrg3:isAmountNormalized>false</nrg3:isAmountNormalized>
							<nrg3:timeDependentAmount xlink:type="simple">
								<nrg3:MonthlyTimeSeries gml:id="id_monthly_ts_pv_production_1">
									<gml:description xlink:type="simple">Monthly PV energy production for pv_panel_1</gml:description>
									<gml:name>MonthlyTimeSeries pv_panel_1</gml:name>
									<nrg3:interpolationType>averageInSucceedingInterval</nrg3:interpolationType>
									<nrg3:startDate>2022-01-01</nrg3:startDate>
									<nrg3:endDate>2025-07-01</nrg3:endDate>
									<nrg3:valuesList uom="kWh">374.0 370.0 390.0 904.0 936.0 904.0 513.0 513.0 496.0 514.0 496.0 513.0 277.0 252.0 277.0 887.0 910.0 884.0 731.0 732.0 708.0 149.0 142.0 149.0 229.0 215.0 229.0 679.0 702.0 679.0 686.0 694.0 671.0 213.0 143.0 147.0 311.0 283.0 311.0 901.0 955.0 928.0</nrg3:valuesList>
								</nrg3:MonthlyTimeSeries>
							</nrg3:timeDependentAmount>
							<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyTypeValue.xml">finalEnergy</nrg3:type>
							<nrg3:endUse codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyEndUseValue.xml">electricalAppliances</nrg3:endUse>
							<nrg3:energyCarrier codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyCarrierValue.xml">electricity</nrg3:energyCarrier>
							<nrg3:source codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergySourceValue.xml">solarEnergy</nrg3:source>
						</nrg3:Energy>
					</nrg3:resource>
					<nrg3:relatedTo>
						<nrg3:CityObjectRelation>
							<nrg3:relationType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/RelationTypeValue.xml">installedOn</nrg3:relationType>
							<nrg3:relatedTo xlink:type="simple" xlink:href="#id_building_1_RoofSurface2_7"/>
						</nrg3:CityObjectRelation>
					</nrg3:relatedTo>
					<nrg3:relatedTo>
						<nrg3:CityObjectRelation>
							<nrg3:relationType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/RelationTypeValue.xml">installedOn</nrg3:relationType>
							<nrg3:relatedTo xlink:type="simple" xlink:href="#id_building_1_RoofSurface2_6"/>
						</nrg3:CityObjectRelation>
					</nrg3:relatedTo>
					<nrg3:model>PV-16-270 PW</nrg3:model>
					<nrg3:yearOfInstallation>2020</nrg3:yearOfInstallation>
					<nrg3:numberOfDevices>36</nrg3:numberOfDevices>
					<nrg3:installedPower uom="W">9720.0</nrg3:installedPower>
					<nrg3:azimuth uom="deg">235.65</nrg3:azimuth>
					<nrg3:inclination uom="deg">44.51</nrg3:inclination>
					<nrg3:lod2MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="pv_panel_1_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85183.19305294828 446879.7487571072 3.00302426150856 85186.65607630825 446882.19977102155 7.245664948627841 85192.37540055497 446874.11897092743 7.245664948627841 85188.912377195 446871.6679570131 3.00302426150856 85183.19305294828 446879.7487571072 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</nrg3:lod2MultiSurface>
					<nrg3:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="pv_panel_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.14626287686 446878.4264519866 3.0171663971323 85184.70034661447 446878.81861421285 3.69598890707138 85183.77023428747 446880.1327645312 3.69598890707139 85183.21615054988 446879.7406023049 3.0171663971323 85184.14626287686 446878.4264519866 3.0171663971323</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_2">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.09948358465 446877.0796519709 3.01716639713229 85185.65356732225 446877.4718141972 3.69598890707137 85184.72345499526 446878.7859645155 3.69598890707137 85184.16937125767 446878.3938022892 3.01716639713229 85185.09948358465 446877.0796519709 3.01716639713229</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_3">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.05270429244 446875.7328519552 3.01716639713229 85186.60678803004 446876.1250141815 3.69598890707137 85185.67667570304 446877.4391644998 3.69598890707137 85185.12259196545 446877.04700227355 3.01716639713229 85186.05270429244 446875.7328519552 3.01716639713229</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_4">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.00592500024 446874.3860519395 3.0171663971323 85187.56000873783 446874.7782141658 3.69598890707138 85186.62989641084 446876.09236448415 3.69598890707139 85186.07581267324 446875.70020225784 3.0171663971323 85187.00592500024 446874.3860519395 3.0171663971323</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_5">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.95914570802 446873.03925192385 3.0171663971323 85188.51322944561 446873.4314141501 3.69598890707138 85187.58311711863 446874.74556446844 3.69598890707139 85187.02903338103 446874.3534022422 3.0171663971323 85187.95914570802 446873.03925192385 3.0171663971323</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_6">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.91236641581 446871.69245190814 3.0171663971323 85189.4664501534 446872.08461413445 3.69598890707138 85188.53633782642 446873.3987644528 3.69598890707138 85187.98225408881 446873.00660222647 3.0171663971323 85188.91236641581 446871.69245190814 3.0171663971323</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_7">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.72343343687 446878.8349543056 3.72427317831883 85185.27751717446 446879.2271165319 4.40309568825792 85184.34740484747 446880.54126685025 4.40309568825792 85183.79332110987 446880.149104624 3.72427317831883 85184.72343343687 446878.8349543056 3.72427317831883</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_8">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.67665414466 446877.48815428995 3.72427317831883 85186.23073788224 446877.88031651627 4.40309568825792 85185.30062555526 446879.1944668346 4.40309568825792 85184.74654181766 446878.8023046083 3.72427317831883 85185.67665414466 446877.48815428995 3.72427317831883</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_9">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.62987485244 446876.1413542743 3.72427317831884 85187.18395859003 446876.53351650055 4.40309568825792 85186.25384626305 446877.8476668189 4.40309568825792 85185.69976252544 446877.4555045926 3.72427317831884 85186.62987485244 446876.1413542743 3.72427317831884</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_10">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.58309556023 446874.7945542586 3.72427317831885 85188.13717929782 446875.1867164849 4.40309568825793 85187.20706697083 446876.5008668032 4.40309568825793 85186.65298323323 446876.1087045769 3.72427317831885 85187.58309556023 446874.7945542586 3.72427317831885</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_11">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.53631626802 446873.44775424286 3.72427317831883 85189.0904000056 446873.8399164692 4.403095688257911 85188.16028767862 446875.1540667875 4.40309568825792 85187.60620394102 446874.76190456125 3.72427317831883 85188.53631626802 446873.44775424286 3.72427317831883</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_12">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.4895369758 446872.1009542272 3.72427317831884 85190.04362071339 446872.4931164535 4.40309568825792 85189.1135083864 446873.80726677185 4.40309568825792 85188.5594246488 446873.41510454554 3.72427317831884 85189.4895369758 446872.1009542272 3.72427317831884</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_13">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.30060399686 446879.2434566247 4.431379959505381 85185.85468773445 446879.635618851 5.11020246944447 85184.92457540747 446880.9497691693 5.11020246944447 85184.37049166986 446880.557606943 4.431379959505381 85185.30060399686 446879.2434566247 4.431379959505381</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_14">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.25382470465 446877.896656609 4.43137995950537 85186.80790844224 446878.2888188353 5.11020246944446 85185.87779611525 446879.6029691536 5.11020246944446 85185.32371237765 446879.21080692735 4.43137995950537 85186.25382470465 446877.896656609 4.43137995950537</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_15">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.20704541243 446876.5498565933 4.43137995950537 85187.76112915002 446876.9420188196 5.11020246944446 85186.83101682304 446878.25616913795 5.11020246944446 85186.27693308544 446877.86400691164 4.43137995950537 85187.20704541243 446876.5498565933 4.43137995950537</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_16">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.16026612022 446875.20305657765 4.4313799595054 85188.71434985782 446875.5952188039 5.110202469444481 85187.78423753082 446876.90936912224 5.110202469444481 85187.23015379324 446876.517206896 4.4313799595054 85188.16026612022 446875.20305657765 4.4313799595054</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_17">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.113486828 446873.85625656194 4.431379959505381 85189.66757056561 446874.24841878825 5.11020246944447 85188.73745823861 446875.5625691066 5.11020246944447 85188.18337450102 446875.17040688026 4.431379959505381 85189.113486828 446873.85625656194 4.431379959505381</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_18">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85190.06670753579 446872.5094565463 4.431379959505381 85190.6207912734 446872.90161877254 5.11020246944447 85189.6906789464 446874.21576909086 5.11020246944447 85189.13659520881 446873.8236068646 4.431379959505381 85190.06670753579 446872.5094565463 4.431379959505381</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_19">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.87777455685 446879.65195894375 5.13848674069194 85186.43185829445 446880.04412117007 5.817309250631021 85185.50174596746 446881.3582714884 5.817309250631021 85184.94766222987 446880.9661092621 5.13848674069194 85185.87777455685 446879.65195894375 5.13848674069194</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_20">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.83099526464 446878.30515892804 5.13848674069193 85187.38507900224 446878.69732115435 5.81730925063101 85186.45496667524 446880.0114714727 5.81730925063101 85185.90088293765 446879.6193092464 5.13848674069193 85186.83099526464 446878.30515892804 5.13848674069193</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_21">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.78421597242 446876.9583589124 5.13848674069193 85188.33829971003 446877.3505211387 5.81730925063101 85187.40818738303 446878.664671457 5.81730925063101 85186.85410364544 446878.2725092307 5.13848674069193 85187.78421597242 446876.9583589124 5.13848674069193</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_22">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.73743668023 446875.61155889666 5.13848674069194 85189.29152041781 446876.003721123 5.817309250631021 85188.36140809083 446877.3178714413 5.817309250631021 85187.80732435323 446876.92570921505 5.13848674069194 85188.73743668023 446875.61155889666 5.13848674069194</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_23">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.69065738801 446874.264758881 5.13848674069194 85190.2447411256 446874.6569211073 5.817309250631021 85189.31462879862 446875.97107142565 5.817309250631021 85188.76054506101 446875.57890919934 5.13848674069194 85189.69065738801 446874.264758881 5.13848674069194</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_24">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85190.6438780958 446872.91795886535 5.13848674069194 85191.19796183339 446873.3101210916 5.817309250631021 85190.2678495064 446874.62427140994 5.817309250631021 85189.7137657688 446874.2321091837 5.13848674069194 85190.6438780958 446872.91795886535 5.13848674069194</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_25">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.45494511686 446880.0604612628 5.84559352187848 85187.00902885445 446880.4526234891 6.524416031817561 85186.07891652746 446881.7667738074 6.524416031817561 85185.52483278986 446881.37461158115 5.84559352187848 85186.45494511686 446880.0604612628 5.84559352187848</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_26">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.40816582464 446878.7136612471 5.84559352187848 85187.96224956223 446879.1058234734 6.524416031817561 85187.03213723525 446880.41997379175 6.524416031817561 85186.47805349765 446880.02781156544 5.84559352187848 85187.40816582464 446878.7136612471 5.84559352187848</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_27">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.36138653243 446877.36686123145 5.84559352187847 85188.91547027002 446877.7590234577 6.524416031817561 85187.98535794303 446879.07317377604 6.524416031817561 85187.43127420543 446878.6810115498 5.84559352187848 85188.36138653243 446877.36686123145 5.84559352187847</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_28">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.31460724022 446876.02006121574 5.845593521878491 85189.8686909778 446876.41222344205 6.52441603181757 85188.93857865082 446877.7263737604 6.52441603181757 85188.38449491322 446877.33421153406 5.845593521878491 85189.31460724022 446876.02006121574 5.845593521878491</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_29">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85190.267827948 446874.6732612001 5.84559352187848 85190.82191168559 446875.06542342633 6.524416031817561 85189.89179935861 446876.37957374466 6.524416031817561 85189.337715621 446875.9874115184 5.84559352187848 85190.267827948 446874.6732612001 5.84559352187848</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_30">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85191.22104865579 446873.32646118436 5.84559352187848 85191.77513239338 446873.7186234107 6.524416031817561 85190.8450200664 446875.032773729 6.524416031817561 85190.29093632879 446874.6406115027 5.84559352187848 85191.22104865579 446873.32646118436 5.84559352187848</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_31">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.03211567685 446880.46896358184 6.552700303065031 85187.58619941444 446880.86112580815 7.23152281300411 85186.65608708745 446882.1752761265 7.23152281300411 85186.10200334985 446881.7831139002 6.552700303065031 85187.03211567685 446880.46896358184 6.552700303065031</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_32">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.98533638463 446879.1221635662 6.552700303065031 85188.53942012222 446879.5143257925 7.23152281300411 85187.60930779524 446880.8284761108 7.23152281300411 85187.05522405764 446880.4363138845 6.552700303065031 85187.98533638463 446879.1221635662 6.552700303065031</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_33">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.93855709242 446877.7753635505 6.552700303065031 85189.49264083001 446878.1675257768 7.23152281300411 85188.56252850303 446879.4816760951 7.23152281300411 85188.00844476542 446879.08951386885 6.552700303065031 85188.93855709242 446877.7753635505 6.552700303065031</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_34">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.8917778002 446876.4285635348 6.55270030306504 85190.44586153781 446876.8207257611 7.23152281300412 85189.51574921081 446878.13487607945 7.23152281300412 85188.96166547322 446877.74271385313 6.55270030306504 85189.8917778002 446876.4285635348 6.55270030306504</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_35">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85190.844998508 446875.0817635191 6.552700303065031 85191.3990822456 446875.4739257454 7.23152281300411 85190.4689699186 446876.78807606373 7.23152281300411 85189.91488618101 446876.3959138375 6.552700303065031 85190.844998508 446875.0817635191 6.552700303065031</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_36">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85191.79821921578 446873.73496350343 6.552700303065021 85192.35230295338 446874.12712572975 7.23152281300411 85191.42219062638 446875.4412760481 7.23152281300411 85190.8681068888 446875.04911382176 6.552700303065021 85191.79821921578 446873.73496350343 6.552700303065021</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</nrg3:lod3MultiSurface>
					<nrg3:cellType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CellTypeValue.xml">unknown</nrg3:cellType>
				</nrg3:PhotovoltaicCollector>
			</nrg3:device>
			<nrg3:device xlink:type="simple">
				<nrg3:HeatPump gml:id="heat_pump_1">
					<gml:description xlink:type="simple">NIBE F1255 PC water-water heat pump (geothermal), source 24 °C / system 31 °C, water distribution medium</gml:description>
					<gml:name>NIBE F1255 PC</gml:name>
					<core:creationDate>2026-04-13</core:creationDate>
					<nrg3:identifier codeSpace="https://www.nibe.eu/nl-nl/producten/warmtepompen/water-water-warmtepompen/f1255-pc">F1255 PC</nrg3:identifier>
					<nrg3:model>NIBE F1255 PC</nrg3:model>
					<nrg3:numberOfDevices>1</nrg3:numberOfDevices>
					<nrg3:installedPower uom="W">6000.0</nrg3:installedPower>
					<nrg3:heatSource codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/HeatSourceValue.xml">waterSource</nrg3:heatSource>
					<nrg3:copSourceTemperature uom="degC">24.0</nrg3:copSourceTemperature>
					<nrg3:copOperationTemperature uom="degC">31.0</nrg3:copOperationTemperature>
				</nrg3:HeatPump>
			</nrg3:device>
			<nrg3:device xlink:type="simple">
				<nrg3:EVChargingStation gml:id="id_ev_charging_station_1">
					<gml:description xlink:type="simple">EVHUB AC Mode 3 laadpaal, 3.7-22 kW (32A, 1/3-phase), Type 2 connector with 8m cable. IP55, polycarbonate housing (410x280x150 mm), built-in DC detection. Dedicated to Golf GTE 2015 (8.7 kWh gross / 7.5 kWh net); car-side limit 3.6 kW. ~150 charges/year.</gml:description>
					<gml:name>EVHUB Laadpaal Type 2</gml:name>
					<core:creationDate>2026-04-04</core:creationDate>
					<nrg3:validFrom>2022-07-18T00:00:00</nrg3:validFrom>
					<nrg3:resource xlink:type="simple">
						<nrg3:Energy gml:id="id_ev_energy_1">
							<gml:description xlink:type="simple">Annual electricity consumption for EV charging (Golf GTE 2015, ~150 charges/year x 7.5 kWh net)</gml:description>
							<gml:name>EV charging energy demand</gml:name>
							<nrg3:creationDate>2026-04-10</nrg3:creationDate>
							<nrg3:operationType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ResourceOperationTypeValue.xml">demands</nrg3:operationType>
							<nrg3:referencePeriod codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ReferencePeriodValue.xml">year</nrg3:referencePeriod>
							<nrg3:amount uom="MWh/a">1.125</nrg3:amount>
							<nrg3:year>2025</nrg3:year>
							<nrg3:isAmountNormalized>false</nrg3:isAmountNormalized>
							<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyTypeValue.xml">finalEnergy</nrg3:type>
							<nrg3:endUse codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyEndUseValue.xml">mobility</nrg3:endUse>
							<nrg3:energyCarrier codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyCarrierValue.xml">electricity</nrg3:energyCarrier>
							<nrg3:maximumLoad uom="kW">3.6</nrg3:maximumLoad>
							<nrg3:source codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergySourceValue.xml">powerGrid</nrg3:source>
						</nrg3:Energy>
					</nrg3:resource>
					<nrg3:model>LP-H8T5OIUGL5</nrg3:model>
					<nrg3:yearOfInstallation>2022</nrg3:yearOfInstallation>
					<nrg3:numberOfDevices>1</nrg3:numberOfDevices>
					<nrg3:installedPower uom="W">22000.0</nrg3:installedPower>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingStationTypeValue.xml">AC</nrg3:type>
					<nrg3:chargingSpeedLevel codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingSpeedLevelValue.xml">Level 2</nrg3:chargingSpeedLevel>
					<nrg3:connectorType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingConnectorTypeValue.xml">AC - Mennekes (Type2)</nrg3:connectorType>
					<nrg3:hasLoadManagement>true</nrg3:hasLoadManagement>
					<nrg3:access codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingAccessTypeValue.xml">private</nrg3:access>
				</nrg3:EVChargingStation>
			</nrg3:device>
			<bldg:class codeSpace="http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_class.xml">1000</bldg:class>
			<bldg:function codeSpace="http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_function.xml">1000</bldg:function>
			<bldg:usage codeSpace="http://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_usage.xml">1000</bldg:usage>
			<bldg:yearOfConstruction>2020</bldg:yearOfConstruction>
			<bldg:roofType codeSpace="https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_roofType.xml">1130</bldg:roofType>
			<bldg:storeysAboveGround>3</bldg:storeysAboveGround>
			<bldg:storeysBelowGround>0</bldg:storeysBelowGround>
			<bldg:lod0FootPrint xlink:type="simple">
				<gml:MultiSurface gml:id="id_building_1_lod0" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
					<gml:surfaceMember xlink:type="simple">
						<gml:Polygon gml:id="id_building_1_lod0_poly_1">
							<gml:exterior>
								<gml:LinearRing>
									<gml:posList>85193.08499904633 446869.6749987154 0.105 85199.80511579465 446874.4312767 0.105 85192.18338832188 446885.1999712909 0.105 85185.46327252725 446880.4436945909 0.105 85193.08499904633 446869.6749987154 0.105</gml:posList>
								</gml:LinearRing>
							</gml:exterior>
						</gml:Polygon>
					</gml:surfaceMember>
				</gml:MultiSurface>
			</bldg:lod0FootPrint>
			<bldg:lod1Solid xlink:type="simple">
				<gml:Solid gml:id="id_building_1_lod1" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
					<gml:exterior xlink:type="simple">
						<gml:CompositeSurface gml:id="id_building_1_lod1_shell">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_lod1_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.08499904633 446869.6749987154 -0.38699999999994 85185.46327252725 446880.4436945909 -0.38699999999994 85192.18338832188 446885.1999712909 -0.38699999999994 85199.80511579465 446874.4312767 -0.38699999999994 85193.08499904633 446869.6749987154 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_lod1_poly_2">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85199.80511579465 446874.4312767 -0.38699999999994 85199.80511579465 446874.4312767 9.25110000001437 85193.08499904633 446869.6749987154 9.25110000001437 85193.08499904633 446869.6749987154 -0.38699999999994 85199.80511579465 446874.4312767 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_lod1_poly_3">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.18338832188 446885.1999712909 -0.38699999999994 85192.18338832188 446885.1999712909 9.25110000001437 85199.80511579465 446874.4312767 9.25110000001437 85199.80511579465 446874.4312767 -0.38699999999994 85192.18338832188 446885.1999712909 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_lod1_poly_4">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.46327252725 446880.4436945909 -0.38699999999994 85185.46327252725 446880.4436945909 9.25110000001437 85192.18338832188 446885.1999712909 9.25110000001437 85192.18338832188 446885.1999712909 -0.38699999999994 85185.46327252725 446880.4436945909 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_lod1_poly_5">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.08499904633 446869.6749987154 -0.38699999999994 85193.08499904633 446869.6749987154 9.25110000001437 85185.46327252725 446880.4436945909 9.25110000001437 85185.46327252725 446880.4436945909 -0.38699999999994 85193.08499904633 446869.6749987154 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_lod1_poly_6">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.08499904633 446869.6749987154 9.25110000001437 85199.80511579465 446874.4312767 9.25110000001437 85192.18338832188 446885.1999712909 9.25110000001437 85185.46327252725 446880.4436945909 9.25110000001437 85193.08499904633 446869.6749987154 9.25110000001437</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:CompositeSurface>
					</gml:exterior>
				</gml:Solid>
			</bldg:lod1Solid>
			<bldg:boundedBy xlink:type="simple">
				<bldg:GroundSurface gml:id="id_building_1_GroundSurface2_1">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_ground_floor"/>
					<bldg:lod2MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_GroundSurface2_1_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_GroundSurface2_1_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.08499904633 446869.6749987154 -0.38699999999994 85185.46327252725 446880.4436945909 -0.38699999999994 85192.18338832188 446885.1999712909 -0.38699999999994 85199.80511579465 446874.4312767 -0.38699999999994 85193.08499904633 446869.6749987154 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:GroundSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_1">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod2MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_1_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_1_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085 446869.675 5.1575673701116305 85185.46327252725 446880.4436945909 5.15756737011165 85185.46327252725 446880.4436945909 -0.38699999999994 85193.08499904633 446869.6749987154 -0.38699999999994 85193.085 446869.675 5.1575673701116305</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_2">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod2MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_2_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_2_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.18338832188 446885.1999712909 5.11164310860733 85192.18338832188 446885.1999712909 -0.38699999999994 85185.46327252725 446880.4436945909 -0.38699999999994 85185.46327252725 446880.4436945909 5.15756737011165 85188.80455276738 446882.8085427334 9.251100000014391 85192.18338832188 446885.1999712909 5.11164310860733</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_3">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod2MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_3_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_3_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.18338832188 446885.1999712909 5.11164310860733 85199.80511579465 446874.4312767 5.111643108607351 85199.80511579465 446874.4312767 -0.38699999999994 85192.18338832188 446885.1999712909 -0.38699999999994 85192.18338832188 446885.1999712909 5.11164310860733</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_4">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod2MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_4_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_4_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085 446869.675 5.1575673701116305 85193.08499904633 446869.6749987154 -0.38699999999994 85199.80511579465 446874.4312767 -0.38699999999994 85199.80511579465 446874.4312767 5.111643108607351 85196.42628024014 446872.0398481425 9.251100000014391 85193.085 446869.675 5.1575673701116305</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_1">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod2MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_1_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_1_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.18338832188 446885.1999712909 5.11164310860733 85188.80455276738 446882.8085427334 9.251100000014391 85196.42628024014 446872.0398481425 9.251100000014391 85199.80511579465 446874.4312767 5.111643108607351 85192.18338832188 446885.1999712909 5.11164310860733</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_2">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod2MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_2_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_2_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085 446869.675 5.1575673701116305 85196.42628024014 446872.0398481425 9.251100000014391 85188.80455276738 446882.8085427334 9.251100000014391 85185.46327252725 446880.4436945909 5.15756737011165 85193.085 446869.675 5.1575673701116305</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_3">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_3_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85195.21106006154 446871.17975838616 7.762317581980881 85193.54158458892 446868.76972148736 5.007345318032891 85200.46948068505 446873.67305824364 5.007347205355581 85197.64148568557 446872.89993359876 7.7623181937486105 85195.21106006154 446871.17975838616 7.762317581980881</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_4">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_4_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_4_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85195.21106006154 446871.17975838616 7.762317581980881 85197.64148568557 446872.89993359876 7.7623181937486105 85196.1132418234 446872.48213830794 9.251100000014361 85195.21106006154 446871.17975838616 7.762317581980881</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_5">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_5_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_5_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85195.21107388413 446871.1797650943 7.76230333740129 85193.085 446869.675 5.1575673701116305 85193.085 446869.675 0.10500000000002842 85199.80511579465 446874.4312767 0.1050000000000453 85199.80511579465 446874.4312767 5.111643108607341 85197.64149903996 446872.899939998 7.76231910067633 85195.21107388413 446871.1797650943 7.76230333740129</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85198.52404778215 446873.52457893983 4.160000000006811 85197.86289141081 446873.05663422873 4.1600000000068 85197.86289141081 446873.05663422873 5.4400000000087 85198.52404778215 446873.52457893983 5.4400000000087 85198.52404778215 446873.52457893983 4.160000000006811</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85197.67678813591 446872.9249164582 4.1600000000068 85197.0156072773 446872.45695441583 4.1600000000068 85197.0156072773 446872.45695441583 5.4400000000087 85197.67678813591 446872.9249164582 5.4400000000087 85197.67678813591 446872.9249164582 4.1600000000068</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85195.83695320296 446871.6227418691 4.1600000000068 85195.17579683164 446871.15479715803 4.1600000000068 85195.17579683164 446871.15479715803 5.4400000000087 85195.83695320296 446871.6227418691 5.4400000000087 85195.83695320296 446871.6227418691 4.1600000000068</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85194.98969355674 446871.0230793875 4.1600000000068 85194.3285371854 446870.5551346764 4.16000000000679 85194.3285371854 446870.5551346764 5.44000000000869 85194.98969355674 446871.0230793875 5.44000000000869 85194.98969355674 446871.0230793875 4.1600000000068</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85199.46680779313 446874.19183343527 1.18000000000238 85197.915947169 446873.09418534755 1.18000000000238 85197.915947169 446873.09418534755 2.38000000000416 85199.46680779313 446874.19183343527 2.38000000000416 85199.46680779313 446874.19183343527 1.18000000000238</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85194.93663779854 446870.98552826873 1.18000000000237 85193.38577717442 446869.88788018096 1.18000000000237 85193.38577717442 446869.88788018096 2.38000000000415 85194.93663779854 446870.98552826873 2.38000000000415 85194.93663779854 446870.98552826873 1.18000000000237</gml:posList>
										</gml:LinearRing>
									</gml:interior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
					<bldg:opening xlink:type="simple">
						<bldg:Window gml:id="id_building_1_Window2_1">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_window_hr"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Window2_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Window2_1_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85197.91594692231 446873.09418373107 1.18000000000238 85199.46680754643 446874.19183181884 1.18000000000238 85199.46680754643 446874.19183181884 2.38000000000416 85197.91594692231 446873.09418373107 2.38000000000416 85197.91594692231 446873.09418373107 1.18000000000238</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening xlink:type="simple">
						<bldg:Window gml:id="id_building_1_Window2_2">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_window_hr"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Window2_2_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Window2_2_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85193.38577721616 446869.8878818595 1.18000000000237 85194.93663784028 446870.98552994727 1.18000000000237 85194.93663784028 446870.98552994727 2.38000000000415 85193.38577721616 446869.8878818595 2.38000000000415 85193.38577721616 446869.8878818595 1.18000000000237</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening xlink:type="simple">
						<bldg:Window gml:id="id_building_1_Window2_3">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_window_hr"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Window2_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Window2_3_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85197.86289239576 446873.05663422873 4.160000000006811 85198.5240487671 446873.52457893983 4.1600000000068 85198.5240487671 446873.52457893983 5.4400000000087 85197.86289239576 446873.05663422873 5.4400000000087 85197.86289239576 446873.05663422873 4.160000000006811</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening xlink:type="simple">
						<bldg:Window gml:id="id_building_1_Window2_4">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_window_hr"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Window2_4_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Window2_4_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85197.01560743332 446872.45695557585 4.1600000000068 85197.67678829194 446872.9249176182 4.1600000000068 85197.67678829194 446872.9249176182 5.4400000000087 85197.01560743332 446872.45695557585 5.4400000000087 85197.01560743332 446872.45695557585 4.1600000000068</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening xlink:type="simple">
						<bldg:Window gml:id="id_building_1_Window2_5">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_window_hr"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Window2_5_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Window2_5_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85195.17579647065 446871.15479569434 4.1600000000068 85195.83695284199 446871.62274040544 4.1600000000068 85195.83695284199 446871.62274040544 5.4400000000087 85195.17579647065 446871.15479569434 5.4400000000087 85195.17579647065 446871.15479569434 4.1600000000068</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening xlink:type="simple">
						<bldg:Window gml:id="id_building_1_Window2_6">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_window_hr"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Window2_6_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Window2_6_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85194.32853694916 446870.5551329136 4.1600000000068 85194.9896933205 446871.0230776247 4.16000000000679 85194.9896933205 446871.0230776247 5.44000000000869 85194.32853694916 446870.5551329136 5.44000000000869 85194.32853694916 446870.5551329136 4.1600000000068</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_5">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_5_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_5_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85197.64149296742 446872.89993570006 7.7623265402442705 85199.80511579465 446874.4312767 5.111643108607341 85192.18338832188 446885.1999712909 5.11164310860733 85188.80455276738 446882.8085427334 9.251100000014391 85196.1132418234 446872.48213830794 9.2511000000144 85197.64149296742 446872.89993570006 7.7623265402442705</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_6">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_6_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_6_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85196.1132418234 446872.48213830794 9.251100000014361 85188.80455276738 446882.8085427334 9.251100000014391 85185.46327252725 446880.4436945909 5.15756737011165 85193.085 446869.675 5.1575673701116305 85195.21106751285 446871.17976058496 7.76229553169855 85196.1132418234 446872.48213830794 9.251100000014361</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_7">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_7_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_7_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85195.21106751285 446871.17976058496 7.762295531698401 85193.085 446869.675 5.15756737011164 85185.46327252725 446880.4436945909 5.15756737011165 85188.80455276738 446882.8085427334 9.2511000000144 85188.19016447008 446883.67660839926 9.2511000000144 85182.94780530749 446879.96623918833 2.82848149826521 85188.92709883816 446871.518129999 2.82848149826518 85190.67202397605 446872.75313056004 4.9662580940358705 85193.508115551 446868.7460332043 4.96625809403585 85193.54161846638 446868.7697454647 5.00730381348992 85195.21106751285 446871.17976058496 7.762295531698401</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_8">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_8_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_8_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85200.46948068505 446873.67305824364 5.007347205355581 85200.50298515584 446873.69677160494 4.966300000008051 85191.68760005022 446886.15197814995 4.96630000000804 85188.19016447008 446883.67660839926 9.2511000000144 85188.80455276738 446882.8085427334 9.251100000014391 85192.18338832188 446885.1999712909 5.11164310860733 85199.80511579465 446874.4312767 5.111643108607341 85197.64149296738 446872.8999357 7.7623265402845805 85200.46948068505 446873.67305824364 5.007347205355581</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_9">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_9_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_9_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85200.91877905159 446873.99105683435 2.56980000000448 85192.10339394597 446886.4462633794 2.56980000000447 85191.68760005022 446886.15197814995 4.96630000000804 85200.50298515584 446873.69677160494 4.966300000008051 85200.91877905159 446873.99105683435 2.56980000000448</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_10">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_reed_roof"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_10_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_10_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.09229561256 446868.4517295427 2.56980000000449 85193.50808134588 446868.74600899505 4.966300000008051 85190.67198977093 446872.7531063508 4.966300000008051 85190.2562040376 446872.4588268985 2.56980000000449 85193.09229561256 446868.4517295427 2.56980000000449</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_6">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_6_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_6_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.08499904633 446869.6749987154 0.1050000000000453 85193.08499904633 446869.6749987154 -0.386999999999924 85199.80511484097 446874.4312754154 -0.38699999999994 85199.80511484097 446874.4312754154 0.10500000000002842 85193.08499904633 446869.6749987154 0.1050000000000453</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_7">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_7_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_7_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85199.80511579465 446874.4312767 0.10500000000003108 85199.80511579465 446874.4312767 -0.386999999999924 85192.18338832188 446885.1999712909 -0.386999999999924 85192.18338832188 446885.1999712909 0.10500000000003108 85199.80511579465 446874.4312767 0.10500000000003108</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_8">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_8_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_8_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.18338832188 446885.1999712909 0.10500000000003108 85192.18338832188 446885.1999712909 -0.386999999999924 85185.46327252725 446880.4436945909 -0.386999999999924 85185.46327252725 446880.4436945909 0.10500000000003819 85192.18338832188 446885.1999712909 0.10500000000003108</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_9">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_9_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_9_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.46327252725 446880.4436945909 0.1050000000000071 85185.46327252725 446880.4436945909 -0.38699999999994 85193.085 446869.675 -0.38699999999994 85193.085 446869.675 0.105 85185.46327252725 446880.4436945909 0.1050000000000071</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_10">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_10_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_10_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.18338832188 446885.1999712909 0.10500000000003108 85185.46327252725 446880.4436945909 0.10500000000003819 85185.46327252725 446880.4436945909 5.15756737011165 85188.80455276738 446882.8085427334 9.25110000001437 85192.18338832188 446885.1999712909 5.111643108607341 85192.18338832188 446885.1999712909 0.10500000000003108</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85186.00484121962 446880.8269990802 0.1790000000009031 85188.1882897299 446882.3723720459 0.1790000000009031 85188.1882897299 446882.3723720459 2.7700000000047598 85186.00484121962 446880.8269990802 2.7700000000047598 85186.00484121962 446880.8269990802 0.1790000000009031</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85186.75986547083 446881.3613803861 3.29700000000553 85188.1882897299 446882.3723720459 3.29700000000553 85188.1882897299 446882.3723720459 5.5100000000088105 85186.75986547083 446881.3613803861 5.5100000000088105 85186.75986547083 446881.3613803861 3.29700000000553</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85189.42081580486 446883.24471342086 3.29700000000553 85190.84924006392 446884.25570508064 3.29700000000553 85190.84924006392 446884.25570508064 5.5100000000088105 85189.42081580486 446883.24471342086 5.5100000000088105 85189.42081580486 446883.24471342086 3.29700000000553</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85189.42081580486 446883.24471342086 0.1790000000009031 85191.60426431513 446884.79008638655 0.1790000000009031 85191.60426431513 446884.79008638655 2.7700000000047598 85189.42081580486 446883.24471342086 2.7700000000047598 85189.42081580486 446883.24471342086 0.1790000000009031</gml:posList>
										</gml:LinearRing>
									</gml:interior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
					<bldg:opening xlink:type="simple">
						<bldg:Door gml:id="id_building_1_Door2_1">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_front_door"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_1_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85191.60426956808 446884.79008577345 0.1790000000009031 85189.4208210578 446883.24471280776 0.1790000000009031 85189.4208210578 446883.24471280776 2.7700000000047598 85191.60426956808 446884.79008577345 2.7700000000047598 85191.60426956808 446884.79008577345 0.1790000000009031</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Door>
					</bldg:opening>
					<bldg:opening xlink:type="simple">
						<bldg:Door gml:id="id_building_1_Door2_2">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_front_door"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_2_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_2_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85188.1882897299 446882.3723714855 0.1790000000009031 85186.00484121962 446880.8269985199 0.1790000000009031 85186.00484121962 446880.8269985199 2.7700000000047598 85188.1882897299 446882.3723714855 2.7700000000047598 85188.1882897299 446882.3723714855 0.1790000000009031</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Door>
					</bldg:opening>
					<bldg:opening xlink:type="simple">
						<bldg:Window gml:id="id_building_1_Window2_7">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_window_hr"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Window2_7_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Window2_7_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85188.18828902805 446882.3723720459 3.29700000000553 85186.75986476899 446881.3613803861 3.29700000000553 85186.75986476899 446881.3613803861 5.5100000000088105 85188.18828902805 446882.3723720459 5.5100000000088105 85188.18828902805 446882.3723720459 3.29700000000553</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening xlink:type="simple">
						<bldg:Window gml:id="id_building_1_Window2_8">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_window_hr"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Window2_8_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Window2_8_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85190.84923873509 446884.25570334494 3.29700000000553 85189.42081447602 446883.24471168517 3.29700000000553 85189.42081447602 446883.24471168517 5.5100000000088105 85190.84923873509 446884.25570334494 5.5100000000088105 85190.84923873509 446884.25570334494 3.29700000000553</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_11">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_11_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_11_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85199.80511579465 446874.4312767 0.10500000000003108 85192.18338832188 446885.1999712909 0.10500000000003108 85192.18338832188 446885.1999712909 5.11164310860733 85199.80511579465 446874.4312767 5.11164310860733 85199.80511579465 446874.4312767 0.10500000000003108</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85197.94401879927 446877.06080986274 0.1200000000000174 85197.94401879927 446877.06080986274 2.52300000000358 85197.31778167974 446877.94561666093 2.52300000000358 85197.31778167974 446877.94561666093 0.1200000000000174 85197.94401879927 446877.06080986274 0.1200000000000174</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85196.53498528032 446879.05162515864 0.1310000000000273 85196.53498528032 446879.05162515864 2.52920000000359 85195.62220423891 446880.34128820396 2.52920000000359 85195.62220423891 446880.34128820396 0.1310000000000273 85196.53498528032 446879.05162515864 0.1310000000000273</gml:posList>
										</gml:LinearRing>
									</gml:interior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
					<bldg:opening xlink:type="simple">
						<bldg:Door gml:id="id_building_1_Door2_3">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_back_door"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_3_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85196.53498528032 446879.05162515864 0.1310000000000273 85195.62220423891 446880.34128820396 0.1310000000000273 85195.62220423891 446880.34128820396 2.52920000000359 85196.53498528032 446879.05162515864 2.52920000000359 85196.53498528032 446879.05162515864 0.1310000000000273</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Door>
					</bldg:opening>
					<bldg:opening xlink:type="simple">
						<bldg:Door gml:id="id_building_1_Door2_4">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_back_door"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_4_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_4_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85197.94401879927 446877.06080986274 0.1200000000000174 85197.31778167974 446877.94561666093 0.1200000000000174 85197.31778167974 446877.94561666093 2.52300000000358 85197.94401879927 446877.06080986274 2.52300000000358 85197.94401879927 446877.06080986274 0.1200000000000174</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Door>
					</bldg:opening>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_12">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_external_wall"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_12_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_12_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085 446869.675 0.105 85193.085 446869.675 5.1575673701116305 85185.46327252725 446880.4436945909 5.15756737011165 85185.46327252725 446880.4436945909 0.10500000000003819 85193.085 446869.675 0.105</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85188.81486008388 446875.708255949 0.1790000000001197 85188.81486008388 446875.708255949 2.49700000000356 85189.92983945723 446874.1329080519 2.49700000000356 85189.92983945723 446874.1329080519 0.1790000000001197 85188.81486008388 446875.708255949 0.1790000000001197</gml:posList>
										</gml:LinearRing>
									</gml:interior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
					<bldg:opening xlink:type="simple">
						<bldg:Door gml:id="id_building_1_Door2_5">
							<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_back_door"/>
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_5_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_5_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85188.81486008388 446875.708255949 0.1790000000001197 85189.92983945723 446874.1329080519 0.1790000000001197 85189.92983945723 446874.1329080519 2.49700000000356 85188.81486008388 446875.708255949 2.49700000000356 85188.81486008388 446875.708255949 0.1790000000001197</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Door>
					</bldg:opening>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:GroundSurface gml:id="id_building_1_GroundSurface2_2">
					<nrg3:layeredConstruction xlink:type="simple" xlink:href="#constr_ground_floor"/>
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_GroundSurface2_2_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_GroundSurface2_2_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.46327252725 446880.4436945909 -0.386999999999924 85192.18338832188 446885.1999712909 -0.386999999999924 85199.80511579465 446874.4312767 -0.386999999999924 85193.085 446869.675 -0.386999999999924 85185.46327252725 446880.4436945909 -0.386999999999924</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:GroundSurface>
			</bldg:boundedBy>
			<nrg3:zone xlink:type="simple">
				<nrg3:Zone gml:id="zone_1">
					<gml:description xlink:type="simple">Residential thermal zone with three storeys</gml:description>
					<gml:name>Building zone</gml:name>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CurrentUseValue.xml">residential</nrg3:type>
					<nrg3:coincidesWithLod2Hull>false</nrg3:coincidesWithLod2Hull>
					<nrg3:coincidesWithLod3Hull>true</nrg3:coincidesWithLod3Hull>
					<nrg3:zonePart xlink:type="simple">
						<nrg3:ZonePart gml:id="zone_part_1">
							<gml:description xlink:type="simple">Ground floor, heated and cooled year-round at 22 °C</gml:description>
							<gml:name>Ground floor</gml:name>
							<nrg3:lod3Solid xlink:type="simple">
								<gml:Solid gml:id="zone_part_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:exterior xlink:type="simple">
										<gml:CompositeSurface gml:id="zone_part_1_lod3_shell">
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_1">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85197.91594692231 446873.09418373107 1.18000000000238 85199.46680754643 446874.19183181884 1.18000000000238 85199.46680754643 446874.19183181884 2.38000000000416 85197.91594692231 446873.09418373107 2.38000000000416 85197.91594692231 446873.09418373107 1.18000000000238</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_2">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.38577721616 446869.8878818595 1.18000000000237 85194.93663784028 446870.98552994727 1.18000000000237 85194.93663784028 446870.98552994727 2.38000000000415 85193.38577721616 446869.8878818595 2.38000000000415 85193.38577721616 446869.8878818595 1.18000000000237</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_3">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85192.18338832188 446885.1999712909 3.21300000000006 85192.18338832188 446885.1999712909 0.10500000000003108 85185.46327252725 446880.4436945909 0.10500000000003819 85185.46327252725 446880.4436945909 3.21300000000007 85192.18338832188 446885.1999712909 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85186.00484121962 446880.8269990802 0.1790000000009031 85188.1882897299 446882.3723720459 0.1790000000009031 85188.1882897299 446882.3723720459 2.7700000000047598 85186.00484121962 446880.8269990802 2.7700000000047598 85186.00484121962 446880.8269990802 0.1790000000009031</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85189.42081580486 446883.24471342086 0.1790000000009031 85191.60426431513 446884.79008638655 0.1790000000009031 85191.60426431513 446884.79008638655 2.7700000000047598 85189.42081580486 446883.24471342086 2.7700000000047598 85189.42081580486 446883.24471342086 0.1790000000009031</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_4">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.085 446869.675 3.21300000000006 85193.085 446869.675 0.10500000000002842 85199.80511579465 446874.4312767 0.1050000000000453 85199.80511579465 446874.4312767 3.21300000000006 85193.085 446869.675 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85199.46680779313 446874.19183343527 1.18000000000238 85197.915947169 446873.09418534755 1.18000000000238 85197.915947169 446873.09418534755 2.38000000000416 85199.46680779313 446874.19183343527 2.38000000000416 85199.46680779313 446874.19183343527 1.18000000000238</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85194.93663779854 446870.98552826873 1.18000000000237 85193.38577717442 446869.88788018096 1.18000000000237 85193.38577717442 446869.88788018096 2.38000000000415 85194.93663779854 446870.98552826873 2.38000000000415 85194.93663779854 446870.98552826873 1.18000000000237</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_5">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85199.80511579465 446874.4312767 3.21300000000006 85199.80511579465 446874.4312767 0.10500000000003108 85192.18338832188 446885.1999712909 0.10500000000003108 85192.18338832188 446885.1999712909 3.21300000000006 85199.80511579465 446874.4312767 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85197.94401879927 446877.06080986274 0.1200000000000174 85197.94401879927 446877.06080986274 2.52300000000358 85197.31778167974 446877.94561666093 2.52300000000358 85197.31778167974 446877.94561666093 0.1200000000000174 85197.94401879927 446877.06080986274 0.1200000000000174</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85196.53498528032 446879.05162515864 0.1310000000000273 85196.53498528032 446879.05162515864 2.52920000000359 85195.62220423891 446880.34128820396 2.52920000000359 85195.62220423891 446880.34128820396 0.1310000000000273 85196.53498528032 446879.05162515864 0.1310000000000273</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_6">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85185.46327252725 446880.4436945909 3.21300000000006 85185.46327252725 446880.4436945909 0.10500000000003819 85193.085 446869.675 0.105 85193.085 446869.675 3.21300000000006 85185.46327252725 446880.4436945909 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85188.81486008388 446875.708255949 0.1790000000001197 85188.81486008388 446875.708255949 2.49700000000356 85189.92983945723 446874.1329080519 2.49700000000356 85189.92983945723 446874.1329080519 0.1790000000001197 85188.81486008388 446875.708255949 0.1790000000001197</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_7">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.08499904633 446869.6749987154 3.21300000000006 85199.80511579465 446874.4312767 3.21300000000006 85192.18338832188 446885.1999712909 3.21300000000006 85185.46327252725 446880.4436945909 3.21300000000006 85193.08499904633 446869.6749987154 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_8">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.08499904633 446869.6749987154 -0.38699999999994 85185.46327252725 446880.4436945909 -0.38699999999994 85192.18338832188 446885.1999712909 -0.38699999999994 85199.80511579465 446874.4312767 -0.38699999999994 85193.08499904633 446869.6749987154 -0.38699999999994</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_9">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.60426956808 446884.79008577345 0.1790000000009031 85189.4208210578 446883.24471280776 0.1790000000009031 85189.4208210578 446883.24471280776 2.7700000000047598 85191.60426956808 446884.79008577345 2.7700000000047598 85191.60426956808 446884.79008577345 0.1790000000009031</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_10">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85188.1882897299 446882.3723714855 0.1790000000009031 85186.00484121962 446880.8269985199 0.1790000000009031 85186.00484121962 446880.8269985199 2.7700000000047598 85188.1882897299 446882.3723714855 2.7700000000047598 85188.1882897299 446882.3723714855 0.1790000000009031</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_11">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.08499904633 446869.6749987154 0.1050000000000453 85193.08499904633 446869.6749987154 -0.386999999999924 85199.80511484097 446874.4312754154 -0.38699999999994 85199.80511484097 446874.4312754154 0.10500000000002842 85193.08499904633 446869.6749987154 0.1050000000000453</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_12">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85196.53498528032 446879.05162515864 0.1310000000000273 85195.62220423891 446880.34128820396 0.1310000000000273 85195.62220423891 446880.34128820396 2.52920000000359 85196.53498528032 446879.05162515864 2.52920000000359 85196.53498528032 446879.05162515864 0.1310000000000273</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_13">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85197.94401879927 446877.06080986274 0.1200000000000174 85197.31778167974 446877.94561666093 0.1200000000000174 85197.31778167974 446877.94561666093 2.52300000000358 85197.94401879927 446877.06080986274 2.52300000000358 85197.94401879927 446877.06080986274 0.1200000000000174</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_14">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85199.80511579465 446874.4312767 0.10500000000003108 85199.80511579465 446874.4312767 -0.386999999999924 85192.18338832188 446885.1999712909 -0.386999999999924 85192.18338832188 446885.1999712909 0.10500000000003108 85199.80511579465 446874.4312767 0.10500000000003108</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_15">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85192.18338832188 446885.1999712909 0.10500000000003108 85192.18338832188 446885.1999712909 -0.386999999999924 85185.46327252725 446880.4436945909 -0.386999999999924 85185.46327252725 446880.4436945909 0.10500000000003819 85192.18338832188 446885.1999712909 0.10500000000003108</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_16">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85185.46327252725 446880.4436945909 0.1050000000000071 85185.46327252725 446880.4436945909 -0.38699999999994 85193.085 446869.675 -0.38699999999994 85193.085 446869.675 0.105 85185.46327252725 446880.4436945909 0.1050000000000071</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_1_lod3_poly_17">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85188.81486008388 446875.708255949 0.1790000000001197 85189.92983945723 446874.1329080519 0.1790000000001197 85189.92983945723 446874.1329080519 2.49700000000356 85188.81486008388 446875.708255949 2.49700000000356 85188.81486008388 446875.708255949 0.1790000000001197</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
										</gml:CompositeSurface>
									</gml:exterior>
								</gml:Solid>
							</nrg3:lod3Solid>
							<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CurrentUseValue.xml">residential</nrg3:type>
							<nrg3:isCooled>true</nrg3:isCooled>
							<nrg3:isHeated>true</nrg3:isHeated>
							<nrg3:coincidesWithLod2Hull>false</nrg3:coincidesWithLod2Hull>
							<nrg3:coincidesWithLod3Hull>false</nrg3:coincidesWithLod3Hull>
							<nrg3:heatingSchedule xlink:type="simple">
								<nrg3:ConstantValueSchedule gml:id="zone_part_1_heating_schedule">
									<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ScheduleTypeValue.xml">typicalYear</nrg3:type>
									<nrg3:value uom="°C">22.0</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:heatingSchedule>
							<nrg3:coolingSchedule xlink:type="simple">
								<nrg3:ConstantValueSchedule gml:id="zone_part_1_cooling_schedule">
									<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ScheduleTypeValue.xml">typicalYear</nrg3:type>
									<nrg3:value uom="°C">24.0</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:coolingSchedule>
						</nrg3:ZonePart>
					</nrg3:zonePart>
					<nrg3:zonePart xlink:type="simple">
						<nrg3:ZonePart gml:id="zone_part_2">
							<gml:description xlink:type="simple">First floor, heated to 18 °C when cold outside</gml:description>
							<gml:name>First floor</gml:name>
							<nrg3:lod3Solid xlink:type="simple">
								<gml:Solid gml:id="zone_part_2_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:exterior xlink:type="simple">
										<gml:CompositeSurface gml:id="zone_part_2_lod3_shell">
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_1">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85197.86289239576 446873.05663422873 4.160000000006811 85198.5240487671 446873.52457893983 4.1600000000068 85198.5240487671 446873.52457893983 5.4400000000087 85197.86289239576 446873.05663422873 5.4400000000087 85197.86289239576 446873.05663422873 4.160000000006811</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_2">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85197.01560743332 446872.45695557585 4.1600000000068 85197.67678829194 446872.9249176182 4.1600000000068 85197.67678829194 446872.9249176182 5.4400000000087 85197.01560743332 446872.45695557585 5.4400000000087 85197.01560743332 446872.45695557585 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_3">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85195.17579647065 446871.15479569434 4.1600000000068 85195.83695284199 446871.62274040544 4.1600000000068 85195.83695284199 446871.62274040544 5.4400000000087 85195.17579647065 446871.15479569434 5.4400000000087 85195.17579647065 446871.15479569434 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_4">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85194.32853694916 446870.5551329136 4.1600000000068 85194.9896933205 446871.0230776247 4.16000000000679 85194.9896933205 446871.0230776247 5.44000000000869 85194.32853694916 446870.5551329136 5.44000000000869 85194.32853694916 446870.5551329136 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_5">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85188.18828902805 446882.3723720459 3.29700000000553 85186.75986476899 446881.3613803861 3.29700000000553 85186.75986476899 446881.3613803861 5.5100000000088105 85188.18828902805 446882.3723720459 5.5100000000088105 85188.18828902805 446882.3723720459 3.29700000000553</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_6">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85190.84923873509 446884.25570334494 3.29700000000553 85189.42081447602 446883.24471168517 3.29700000000553 85189.42081447602 446883.24471168517 5.5100000000088105 85190.84923873509 446884.25570334494 5.5100000000088105 85190.84923873509 446884.25570334494 3.29700000000553</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_7">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.31705476782 446884.58680892526 6.17300000000006 85186.29210309687 446881.03031357884 6.17300000000006 85193.91383082164 446870.2616186319 6.17300000000006 85198.93878227763 446873.81811428204 6.17300000000006 85191.31705476782 446884.58680892526 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_8">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.91383056964 446870.26161898795 6.173000000000091 85186.29210309687 446881.03031357884 6.17300000000006 85185.46327252725 446880.4436945909 5.15756737011165 85193.085 446869.675 5.1575673701116305 85193.91383056964 446870.26161898795 6.173000000000091</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_9">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.31705476782 446884.58680892526 6.17300000000006 85198.93878224057 446873.8181143344 6.173000000000051 85199.80511579465 446874.4312767 5.111643108607341 85192.18338832188 446885.1999712909 5.11164310860733 85191.31705476782 446884.58680892526 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_10">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85192.18338832188 446885.1999712909 3.21300000000006 85185.46327252725 446880.4436945909 3.21300000000007 85185.46327252725 446880.4436945909 5.15756737011165 85186.29210309687 446881.03031357884 6.17300000000006 85191.31705476782 446884.58680892526 6.17300000000006 85192.18338832188 446885.1999712909 5.111643108607341 85192.18338832188 446885.1999712909 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85186.75986547083 446881.3613803861 3.29700000000553 85188.1882897299 446882.3723720459 3.29700000000553 85188.1882897299 446882.3723720459 5.5100000000088105 85186.75986547083 446881.3613803861 5.5100000000088105 85186.75986547083 446881.3613803861 3.29700000000553</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85189.42081580486 446883.24471342086 3.29700000000553 85190.84924006392 446884.25570508064 3.29700000000553 85190.84924006392 446884.25570508064 5.5100000000088105 85189.42081580486 446883.24471342086 5.5100000000088105 85189.42081580486 446883.24471342086 3.29700000000553</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_11">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.085 446869.675 3.21300000000006 85199.80511579465 446874.4312767 3.21300000000006 85199.80511579465 446874.4312767 5.111643108607341 85198.93878224057 446873.8181143344 6.17300000000006 85193.91383056964 446870.26161898795 6.173000000000091 85193.085 446869.675 5.1575673701116305 85193.085 446869.675 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85198.52404778215 446873.52457893983 4.160000000006811 85197.86289141081 446873.05663422873 4.1600000000068 85197.86289141081 446873.05663422873 5.4400000000087 85198.52404778215 446873.52457893983 5.4400000000087 85198.52404778215 446873.52457893983 4.160000000006811</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85197.67678813591 446872.9249164582 4.1600000000068 85197.0156072773 446872.45695441583 4.1600000000068 85197.0156072773 446872.45695441583 5.4400000000087 85197.67678813591 446872.9249164582 5.4400000000087 85197.67678813591 446872.9249164582 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85195.83695320296 446871.6227418691 4.1600000000068 85195.17579683164 446871.15479715803 4.1600000000068 85195.17579683164 446871.15479715803 5.4400000000087 85195.83695320296 446871.6227418691 5.4400000000087 85195.83695320296 446871.6227418691 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85194.98969355674 446871.0230793875 4.1600000000068 85194.3285371854 446870.5551346764 4.16000000000679 85194.3285371854 446870.5551346764 5.44000000000869 85194.98969355674 446871.0230793875 5.44000000000869 85194.98969355674 446871.0230793875 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_12">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85199.80511579465 446874.4312767 3.21300000000006 85192.18338832188 446885.1999712909 3.21300000000006 85192.18338832188 446885.1999712909 5.11164310860733 85199.80511579465 446874.4312767 5.11164310860733 85199.80511579465 446874.4312767 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_13">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85185.46327252725 446880.4436945909 3.21300000000006 85193.085 446869.675 3.21300000000006 85193.085 446869.675 5.1575673701116305 85185.46327252725 446880.4436945909 5.15756737011165 85185.46327252725 446880.4436945909 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_2_lod3_poly_14">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.08499904633 446869.6749987154 3.21300000000006 85185.46327252725 446880.4436945909 3.21300000000006 85192.18338832188 446885.1999712909 3.21300000000006 85199.80511579465 446874.4312767 3.21300000000006 85193.08499904633 446869.6749987154 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
										</gml:CompositeSurface>
									</gml:exterior>
								</gml:Solid>
							</nrg3:lod3Solid>
							<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CurrentUseValue.xml">residential</nrg3:type>
							<nrg3:isCooled>true</nrg3:isCooled>
							<nrg3:isHeated>true</nrg3:isHeated>
							<nrg3:coincidesWithLod2Hull>false</nrg3:coincidesWithLod2Hull>
							<nrg3:coincidesWithLod3Hull>false</nrg3:coincidesWithLod3Hull>
							<nrg3:heatingSchedule xlink:type="simple">
								<nrg3:ConstantValueSchedule gml:id="zone_part_2_heating_schedule">
									<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ScheduleTypeValue.xml">typicalYear</nrg3:type>
									<nrg3:value uom="°C">18.0</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:heatingSchedule>
							<nrg3:coolingSchedule xlink:type="simple">
								<nrg3:ConstantValueSchedule gml:id="zone_part_2_cooling_schedule">
									<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ScheduleTypeValue.xml">typicalYear</nrg3:type>
									<nrg3:value uom="°C">24.0</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:coolingSchedule>
						</nrg3:ZonePart>
					</nrg3:zonePart>
				</nrg3:Zone>
			</nrg3:zone>
			<nrg3:occupiedBy xlink:type="simple">
				<nrg3:Occupants gml:id="id_occupants_1">
					<gml:description xlink:type="simple">Residents of Han Solo's house</gml:description>
					<gml:name>Occupants 1</gml:name>
					<nrg3:creationDate>2026-04-04</nrg3:creationDate>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/OccupantsTypeValue.xml">residents</nrg3:type>
					<nrg3:numberOfOccupants>6</nrg3:numberOfOccupants>
					<nrg3:heatDissipation uom="W">80.0</nrg3:heatDissipation>
				</nrg3:Occupants>
			</nrg3:occupiedBy>
			<nrg3:bdgType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/BuildingTypeValue.xml">singleFamilyHouse</nrg3:bdgType>
			<nrg3:bdgIsProtected>false</nrg3:bdgIsProtected>
			<nrg3:bdgNumberOfBuildingUnits>1</nrg3:bdgNumberOfBuildingUnits>
			<nrg3:bdgOwnershipType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/OwnershipTypeValue.xml">occupantPrivateOwner</nrg3:bdgOwnershipType>
			<nrg3:bdgOwnerName>Han Solo</nrg3:bdgOwnerName>
			<nrg3:bdgVolume>
				<nrg3:QualifiedVolume>
					<nrg3:description>Building's gross volume derived from the 3D model.</nrg3:description>
					<nrg3:source>3D model (LOD3 STEP geometry)</nrg3:source>
					<nrg3:value uom="m3">823.3</nrg3:value>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/VolumeTypeValue.xml">grossVolume</nrg3:type>
				</nrg3:QualifiedVolume>
			</nrg3:bdgVolume>
			<nrg3:bdgArea>
				<nrg3:QualifiedArea>
					<nrg3:description>Gross floor area as registered in the Dutch BAG (Basisregistratie Adressen en Gebouwen).</nrg3:description>
					<nrg3:source>BAG (oppervlakteverblijfsobject, VBO 0000000000000001)</nrg3:source>
					<nrg3:value uom="m2">122.0</nrg3:value>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/AreaTypeValue.xml">grossFloorArea</nrg3:type>
				</nrg3:QualifiedArea>
			</nrg3:bdgArea>
			<nrg3:bdgArea>
				<nrg3:QualifiedArea>
					<nrg3:description>Gross floor area derived from the RenoDAT 3D measurement model (outer-wall envelope, including internal walls).</nrg3:description>
					<nrg3:source>3D model (LOD3 STEP geometry)</nrg3:source>
					<nrg3:value uom="m2">119.6</nrg3:value>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/AreaTypeValue.xml">grossFloorArea</nrg3:type>
				</nrg3:QualifiedArea>
			</nrg3:bdgArea>
			<nrg3:bdgArea>
				<nrg3:QualifiedArea>
					<nrg3:description>Net (usable) floor area from the RenoDAT 3D measurement model (inside-face of outer walls, minus internal walls).</nrg3:description>
					<nrg3:source>3D model (LOD3 STEP geometry)</nrg3:source>
					<nrg3:value uom="m2">104.2</nrg3:value>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/AreaTypeValue.xml">netFloorArea</nrg3:type>
				</nrg3:QualifiedArea>
			</nrg3:bdgArea>
			<nrg3:bdgHeight>
				<nrg3:QualifiedHeight>
					<nrg3:description>Building height measured from ground-floor level to highest roof point.</nrg3:description>
					<nrg3:source>3D model (LOD3 STEP geometry)</nrg3:source>
					<nrg3:value uom="m">8.75</nrg3:value>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/HeightTypeValue.xml">maxHeightAboveGround</nrg3:type>
				</nrg3:QualifiedHeight>
			</nrg3:bdgHeight>
		</bldg:Building>
	</core:cityObjectMember>
	<core:cityObjectMember xlink:type="simple">
		<nrg3:MaterialLibrary gml:id="material_library_1">
			<gml:description xlink:type="simple">Construction materials for single-family residence</gml:description>
			<gml:name>Material Library</gml:name>
			<nrg3:type>materialLibrary</nrg3:type>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_gypsum_board">
					<gml:name>Gypsum plasterboard</gml:name>
					<nrg3:type>gypsum</nrg3:type>
					<nrg3:isTransparent>false</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">0.25</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">900.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">1000.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_mineral_wool">
					<gml:name>Mineral wool insulation</gml:name>
					<nrg3:type>mineralWool</nrg3:type>
					<nrg3:isTransparent>false</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">0.035</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">30.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">840.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_osb">
					<gml:name>OSB sheathing board</gml:name>
					<nrg3:type>wood</nrg3:type>
					<nrg3:isTransparent>false</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">0.13</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">600.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">1700.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_timber_hsb">
					<gml:name>Structural timber (HSB frame)</gml:name>
					<nrg3:type>wood</nrg3:type>
					<nrg3:isTransparent>false</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">0.13</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">500.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">1600.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_reed_thatch">
					<gml:name>Reed thatch (rieten dak)</gml:name>
					<nrg3:type>thatch</nrg3:type>
					<nrg3:isTransparent>false</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">0.09</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">190.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">1400.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_concrete">
					<gml:name>Reinforced concrete (floor slab)</gml:name>
					<nrg3:type>concrete</nrg3:type>
					<nrg3:isTransparent>false</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">1.8</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">2400.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">840.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_eps">
					<gml:name>EPS floor insulation</gml:name>
					<nrg3:type>looseFilledInsulation</nrg3:type>
					<nrg3:isTransparent>false</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">0.036</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">20.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">1450.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_screed">
					<gml:name>Cement screed with floor heating</gml:name>
					<nrg3:type>concrete</nrg3:type>
					<nrg3:isTransparent>false</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">1.4</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">2000.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">880.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_hr_glass">
					<gml:description xlink:type="simple">Low-e coated float glass, HR++ rated</gml:description>
					<gml:name>HR++ double glazing pane</gml:name>
					<nrg3:type>glass</nrg3:type>
					<nrg3:isTransparent>true</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">1.0</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">2500.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">750.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:Gas gml:id="mat_argon">
					<gml:name>Argon gas (glazing cavity)</gml:name>
					<nrg3:type>argon</nrg3:type>
					<nrg3:isVentilated>false</nrg3:isVentilated>
					<nrg3:rValue uom="m2*K/W">0.16</nrg3:rValue>
				</nrg3:Gas>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:SolidMaterial gml:id="mat_timber_door">
					<gml:name>Insulated timber door panel</gml:name>
					<nrg3:type>wood</nrg3:type>
					<nrg3:isTransparent>false</nrg3:isTransparent>
					<nrg3:thermalConductivity uom="W/(m*K)">0.13</nrg3:thermalConductivity>
					<nrg3:density uom="kg/m3">550.0</nrg3:density>
					<nrg3:specificHeatCapacity uom="J/(kg*K)">1600.0</nrg3:specificHeatCapacity>
				</nrg3:SolidMaterial>
			</nrg3:libraryMember>
		</nrg3:MaterialLibrary>
	</core:cityObjectMember>
	<core:cityObjectMember xlink:type="simple">
		<nrg3:LayeredConstructionLibrary gml:id="construction_library_1">
			<gml:description xlink:type="simple">Layered constructions for single-family residence (Rc walls 5.0, Rc floor 5.0, Rc roof 6.0 m2K/W)</gml:description>
			<gml:name>Construction Library</gml:name>
			<nrg3:type>constructionLibrary</nrg3:type>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:LayeredConstruction gml:id="constr_external_wall">
					<gml:description xlink:type="simple">HSB element insulated: gypsum + mineral wool + OSB. Rc=5.0 m2K/W per arch. spec.</gml:description>
					<gml:name>External wall (HSB timber frame, Rc=5.0)</gml:name>
					<nrg3:type>insulatedWoodenWall</nrg3:type>
					<nrg3:uValue uom="W/(m2*K)">0.2</nrg3:uValue>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_wall_L1">
							<nrg3:thickness uom="m">0.0125</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_gypsum_board"/>
						</nrg3:Layer>
					</nrg3:layer>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_wall_L2">
							<gml:description xlink:type="simple">Mineral wool between HSB timber studs (effective lambda includes thermal bridging)</gml:description>
							<nrg3:thickness uom="m">0.18</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_mineral_wool"/>
						</nrg3:Layer>
					</nrg3:layer>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_wall_L3">
							<nrg3:thickness uom="m">0.018</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_osb"/>
						</nrg3:Layer>
					</nrg3:layer>
				</nrg3:LayeredConstruction>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:LayeredConstruction gml:id="constr_ground_floor">
					<gml:description xlink:type="simple">Insulated concrete ground floor slab with floor heating. Rc=5.0 m2K/W per arch. spec.</gml:description>
					<gml:name>Ground floor (concrete slab + EPS, Rc=5.0)</gml:name>
					<nrg3:type>groundSlab</nrg3:type>
					<nrg3:uValue uom="W/(m2*K)">0.2</nrg3:uValue>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_floor_L1">
							<gml:description xlink:type="simple">Cement screed with embedded floor heating (vloerverwarming)</gml:description>
							<nrg3:thickness uom="m">0.065</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_screed"/>
						</nrg3:Layer>
					</nrg3:layer>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_floor_L2">
							<nrg3:thickness uom="m">0.18</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_eps"/>
						</nrg3:Layer>
					</nrg3:layer>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_floor_L3">
							<nrg3:thickness uom="m">0.2</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_concrete"/>
						</nrg3:Layer>
					</nrg3:layer>
				</nrg3:LayeredConstruction>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:LayeredConstruction gml:id="constr_reed_roof">
					<gml:description xlink:type="simple">Sloped reed-thatched roof over HSB structure. Rc=6.0 m2K/W per arch. spec.</gml:description>
					<gml:name>Reed roof (rieten dak, Rc=6.0)</gml:name>
					<nrg3:type>insulatedThatchRoof</nrg3:type>
					<nrg3:uValue uom="W/(m2*K)">0.167</nrg3:uValue>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_roof_L1">
							<nrg3:thickness uom="m">0.0125</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_gypsum_board"/>
						</nrg3:Layer>
					</nrg3:layer>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_roof_L2">
							<gml:description xlink:type="simple">Mineral wool between timber rafters</gml:description>
							<nrg3:thickness uom="m">0.22</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_mineral_wool"/>
						</nrg3:Layer>
					</nrg3:layer>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_roof_L3">
							<nrg3:thickness uom="m">0.018</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_osb"/>
						</nrg3:Layer>
					</nrg3:layer>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_roof_L4">
							<gml:description xlink:type="simple">Reed thatch exterior (rieten dak)</gml:description>
							<nrg3:thickness uom="m">0.3</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_reed_thatch"/>
						</nrg3:Layer>
					</nrg3:layer>
				</nrg3:LayeredConstruction>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:LayeredConstruction gml:id="constr_window_hr">
					<gml:description xlink:type="simple">HR++ double glazing: 4mm glass / 16mm argon / 4mm low-e glass. U=1.1 W/m2K, ZTA=0.60 per arch. spec.</gml:description>
					<gml:name>Window HR++ (U=1.1, g=0.60)</gml:name>
					<nrg3:type>doubleGlazedWindow</nrg3:type>
					<nrg3:uValue uom="W/(m2*K)">1.1</nrg3:uValue>
					<nrg3:gValue uom="">0.6</nrg3:gValue>
					<nrg3:glazingRatio uom="">0.7</nrg3:glazingRatio>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_window_L1">
							<nrg3:thickness uom="m">0.004</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_hr_glass"/>
						</nrg3:Layer>
					</nrg3:layer>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_window_L2">
							<nrg3:thickness uom="m">0.016</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_argon"/>
						</nrg3:Layer>
					</nrg3:layer>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_window_L3">
							<gml:description xlink:type="simple">Low-e coated inner pane</gml:description>
							<nrg3:thickness uom="m">0.004</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_hr_glass"/>
						</nrg3:Layer>
					</nrg3:layer>
				</nrg3:LayeredConstruction>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:LayeredConstruction gml:id="constr_front_door">
					<gml:description xlink:type="simple">Insulated timber front door. U=1.43 W/m2K incl. frame per arch. spec.</gml:description>
					<gml:name>Front door (U=1.43 incl frame)</gml:name>
					<nrg3:type>insulatedTimberDoor</nrg3:type>
					<nrg3:uValue uom="W/(m2*K)">1.43</nrg3:uValue>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_front_door_L1">
							<nrg3:thickness uom="m">0.054</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_timber_door"/>
						</nrg3:Layer>
					</nrg3:layer>
				</nrg3:LayeredConstruction>
			</nrg3:libraryMember>
			<nrg3:libraryMember xlink:type="simple">
				<nrg3:LayeredConstruction gml:id="constr_back_door">
					<gml:description xlink:type="simple">Insulated timber back door. U=1.64 W/m2K incl. frame per arch. spec.</gml:description>
					<gml:name>Back door (U=1.64 incl frame)</gml:name>
					<nrg3:type>insulatedTimberDoor</nrg3:type>
					<nrg3:uValue uom="W/(m2*K)">1.64</nrg3:uValue>
					<nrg3:layer xlink:type="simple">
						<nrg3:Layer gml:id="constr_back_door_L1">
							<nrg3:thickness uom="m">0.048</nrg3:thickness>
							<nrg3:material xlink:type="simple" xlink:href="#mat_timber_door"/>
						</nrg3:Layer>
					</nrg3:layer>
				</nrg3:LayeredConstruction>
			</nrg3:libraryMember>
		</nrg3:LayeredConstructionLibrary>
	</core:cityObjectMember>
</core:CityModel>
