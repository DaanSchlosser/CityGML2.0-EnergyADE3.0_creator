<?xml version='1.0' encoding='UTF-8'?>
<core:CityModel xmlns:app="http://www.opengis.net/citygml/appearance/2.0" xmlns:bldg="http://www.opengis.net/citygml/building/2.0" xmlns:brid="http://www.opengis.net/citygml/bridge/2.0" xmlns:core="http://www.opengis.net/citygml/2.0" xmlns:dem="http://www.opengis.net/citygml/relief/2.0" xmlns:frn="http://www.opengis.net/citygml/cityfurniture/2.0" xmlns:gen="http://www.opengis.net/citygml/generics/2.0" xmlns:gml="http://www.opengis.net/gml" xmlns:grp="http://www.opengis.net/citygml/cityobjectgroup/2.0" xmlns:luse="http://www.opengis.net/citygml/landuse/2.0" xmlns:nrg3="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0" xmlns:pbase="http://www.opengis.net/citygml/profiles/base/2.0" xmlns:sch="http://www.ascc.net/xml/schematron" xmlns:smil20="http://www.w3.org/2001/SMIL20/" xmlns:smil20lang="http://www.w3.org/2001/SMIL20/Language" xmlns:tex="http://www.opengis.net/citygml/texturedsurface/2.0" xmlns:tran="http://www.opengis.net/citygml/transportation/2.0" xmlns:tun="http://www.opengis.net/citygml/tunnel/2.0" xmlns:veg="http://www.opengis.net/citygml/vegetation/2.0" xmlns:wtr="http://www.opengis.net/citygml/waterbody/2.0" xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
	<gml:description>This is a description</gml:description>
	<gml:name>RenoDAT City</gml:name>
	<gml:boundedBy>
		<gml:Envelope srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
			<gml:lowerCorner>85183.193053 446869.674999 -0.387000</gml:lowerCorner>
			<gml:upperCorner>85199.805116 446885.199971 9.251100</gml:upperCorner>
		</gml:Envelope>
	</gml:boundedBy>
	<core:cityObjectMember>
		<bldg:Building gml:id="id_building_1">
			<gml:name>Han solo's house</gml:name>
			<core:creationDate>2026-04-04</core:creationDate>
			<nrg3:device>
				<nrg3:PhotovoltaicCollector gml:id="pv_panel_1">
					<gml:name>PV collector (36x270 Wp)</gml:name>
					<core:creationDate>2026-04-04</core:creationDate>
					<nrg3:relatedTo>
						<nrg3:CityObjectRelation>
							<nrg3:relationType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/RelationTypeValue.xml">installedOn</nrg3:relationType>
							<nrg3:relatedTo xlink:href="#id_building_1_RoofSurface_3"/>
						</nrg3:CityObjectRelation>
					</nrg3:relatedTo>
					<nrg3:resource>
						<nrg3:Energy gml:id="id_pv_production_1">
							<gml:description>PV energy production for pv_panel_1</gml:description>
							<gml:name>PV Production pv_panel_1</gml:name>
							<nrg3:creationDate>2026-04-04</nrg3:creationDate>
							<nrg3:operationType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ResourceOperationTypeValue.xml">produces</nrg3:operationType>
							<nrg3:isAmountNormalized>false</nrg3:isAmountNormalized>
							<nrg3:timeDependentAmount>
								<nrg3:MonthlyTimeSeries gml:id="id_monthly_ts_pv_production_1">
									<gml:description>Monthly PV energy production for pv_panel_1</gml:description>
									<gml:name>MonthlyTimeSeries pv_panel_1</gml:name>
									<nrg3:interpolationType>averageInSucceedingInterval</nrg3:interpolationType>
									<nrg3:startDate>2022-01-01</nrg3:startDate>
									<nrg3:endDate>2025-07-01</nrg3:endDate>
									<nrg3:valuesList uom="kWh">374 370 390 904 936 904 513 513 496 514 496 513 277 252 277 887 910 884 731 732 708 149 142 149 229 215 229 679 702 679 686 694 671 213 143 147 311 283 311 901 955 928</nrg3:valuesList>
								</nrg3:MonthlyTimeSeries>
							</nrg3:timeDependentAmount>
							<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyTypeValue.xml">finalEnergy</nrg3:type>
							<nrg3:endUse codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyEndUseValue.xml">electricalAppliances</nrg3:endUse>
							<nrg3:energyCarrier codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergyCarrierValue.xml">electricity</nrg3:energyCarrier>
							<nrg3:source codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EnergySourceValue.xml">solarEnergy</nrg3:source>
						</nrg3:Energy>
					</nrg3:resource>
					<nrg3:model>PV-16-270 PW</nrg3:model>
					<nrg3:yearOfInstallation>2020</nrg3:yearOfInstallation>
					<nrg3:numberOfDevices>36</nrg3:numberOfDevices>
					<nrg3:installedPower uom="W">9720</nrg3:installedPower>
					<nrg3:azimuth uom="deg">235.65</nrg3:azimuth>
					<nrg3:inclination uom="deg">44.51</nrg3:inclination>
					<nrg3:lod3MultiSurface>
						<gml:MultiSurface gml:id="pv_panel_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85183.193052948277909 446879.748757107183337 3.00302426150856 85184.146273656064295 446878.401957091526128 3.00302426150856 85184.723444216055213 446878.810459410597105 3.71013104269511 85183.770223508268828 446880.157259426254313 3.71013104269511 85183.193052948277909 446879.748757107183337 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_2">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.146273656064295 446878.401957091526128 3.00302426150856 85185.099494363850681 446877.055157075810712 3.00302426150856 85185.676664923841599 446877.463659394881688 3.71013104269511 85184.723444216055213 446878.810459410597105 3.71013104269511 85184.146273656064295 446878.401957091526128 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_3">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.099494363850681 446877.055157075810712 3.00302426150856 85186.052715071637067 446875.708357060153503 3.00302426150856 85186.629885631627985 446876.116859379224479 3.71013104269511 85185.676664923841599 446877.463659394881688 3.71013104269511 85185.099494363850681 446877.055157075810712 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_4">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.052715071637067 446875.708357060153503 3.00302426150856 85187.005935779423453 446874.361557044438086 3.00302426150856 85187.583106339428923 446874.770059363509063 3.71013104269511 85186.629885631642537 446876.116859379224479 3.71013104269511 85186.052715071637067 446875.708357060153503 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_5">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.005935779423453 446874.361557044438086 3.00302426150856 85187.959156487209839 446873.014757028780878 3.00302426150856 85188.536327047215309 446873.423259347851854 3.71013104269511 85187.583106339428923 446874.770059363509063 3.71013104269511 85187.005935779423453 446874.361557044438086 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_6">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.959156487209839 446873.014757028780878 3.00302426150856 85188.912377194996225 446871.667957013123669 3.00302426150856 85189.489547755001695 446872.076459332136437 3.71013104269511 85188.536327047215309 446873.423259347851854 3.71013104269511 85187.959156487209839 446873.014757028780878 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_7">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85183.770223508268828 446880.157259426254313 3.71013104269511 85184.723444216055213 446878.810459410597105 3.71013104269511 85185.300614776060684 446879.218961729609873 4.41723782388165 85184.347394068274298 446880.56576174532529 4.41723782388165 85183.770223508268828 446880.157259426254313 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_8">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.723444216055213 446878.810459410597105 3.71013104269511 85185.676664923841599 446877.463659394881688 3.71013104269511 85186.25383548384707 446877.872161713952664 4.41723782388165 85185.300614776060684 446879.218961729609873 4.41723782388165 85184.723444216055213 446878.810459410597105 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_9">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.676664923841599 446877.463659394881688 3.71013104269511 85186.629885631627985 446876.116859379224479 3.71013104269511 85187.207056191633455 446876.525361698295455 4.41723782388165 85186.25383548384707 446877.872161713952664 4.41723782388165 85185.676664923841599 446877.463659394881688 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_10">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.629885631642537 446876.116859379224479 3.71013104269511 85187.583106339428923 446874.770059363509063 3.71013104269511 85188.160276899419841 446875.178561682580039 4.41723782388165 85187.207056191633455 446876.525361698237248 4.41723782388165 85186.629885631642537 446876.116859379224479 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_11">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.583106339428923 446874.770059363509063 3.71013104269511 85188.536327047215309 446873.423259347851854 3.71013104269511 85189.113497607206227 446873.831761666864622 4.41723782388165 85188.160276899419841 446875.178561682580039 4.41723782388165 85187.583106339428923 446874.770059363509063 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_12">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.536327047215309 446873.423259347851854 3.71013104269511 85189.489547755001695 446872.076459332136437 3.71013104269511 85190.066718314992613 446872.484961651207414 4.41723782388165 85189.113497607206227 446873.831761666864622 4.41723782388165 85188.536327047215309 446873.423259347851854 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_13">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.347394068274298 446880.56576174532529 4.41723782388165 85185.300614776060684 446879.218961729609873 4.41723782388165 85185.877785336051602 446879.627464048680849 5.124344605068201 85184.924564628265216 446880.974264064396266 5.124344605068201 85184.347394068274298 446880.56576174532529 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_14">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.300614776060684 446879.218961729609873 4.41723782388165 85186.25383548384707 446877.872161713952664 4.41723782388165 85186.831006043837988 446878.280664033023641 5.124344605068201 85185.877785336051602 446879.627464048680849 5.124344605068201 85185.300614776060684 446879.218961729609873 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_15">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.25383548384707 446877.872161713952664 4.41723782388165 85187.207056191633455 446876.525361698295455 4.41723782388165 85187.784226751624374 446876.933864017308224 5.124344605068201 85186.831006043837988 446878.280664033023641 5.124344605068201 85186.25383548384707 446877.872161713952664 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_16">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.207056191633455 446876.525361698237248 4.41723782388165 85188.160276899419841 446875.178561682580039 4.41723782388165 85188.73744745941076 446875.587064001651015 5.124344605068201 85187.784226751624374 446876.933864017308224 5.124344605068201 85187.207056191633455 446876.525361698237248 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_17">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.160276899419841 446875.178561682580039 4.41723782388165 85189.113497607206227 446873.831761666864622 4.41723782388165 85189.690668167197146 446874.240263985935599 5.124344605068201 85188.73744745941076 446875.587064001651015 5.124344605068201 85188.160276899419841 446875.178561682580039 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_18">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.113497607206227 446873.831761666864622 4.41723782388165 85190.066718314992613 446872.484961651207414 4.41723782388165 85190.643888874983531 446872.89346397027839 5.124344605068201 85189.690668167197146 446874.240263985935599 5.124344605068201 85189.113497607206227 446873.831761666864622 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_19">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.924564628265216 446880.974264064396266 5.124344605068201 85185.877785336051602 446879.627464048680849 5.124344605068201 85186.45495589604252 446880.035966367751826 5.83145138625475 85185.501735188256134 446881.382766383409034 5.83145138625475 85184.924564628265216 446880.974264064396266 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_20">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.877785336051602 446879.627464048680849 5.124344605068201 85186.831006043837988 446878.280664033023641 5.124344605068201 85187.408176603828906 446878.689166352036409 5.83145138625475 85186.45495589604252 446880.035966367751826 5.83145138625475 85185.877785336051602 446879.627464048680849 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_21">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.831006043837988 446878.280664033023641 5.124344605068201 85187.784226751624374 446876.933864017308224 5.124344605068201 85188.361397311615292 446877.3423663363792 5.83145138625475 85187.408176603828906 446878.689166352036409 5.83145138625475 85186.831006043837988 446878.280664033023641 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_22">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.784226751624374 446876.933864017308224 5.124344605068201 85188.73744745941076 446875.587064001651015 5.124344605068201 85189.31461801941623 446875.995566320663784 5.83145138625475 85188.361397311629844 446877.3423663363792 5.83145138625475 85187.784226751624374 446876.933864017308224 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_23">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.73744745941076 446875.587064001651015 5.124344605068201 85189.690668167197146 446874.240263985935599 5.124344605068201 85190.267838727202616 446874.648766305006575 5.83145138625475 85189.31461801941623 446875.995566320663784 5.83145138625475 85188.73744745941076 446875.587064001651015 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_24">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.690668167197146 446874.240263985935599 5.124344605068201 85190.643888874983531 446872.89346397027839 5.124344605068201 85191.221059434989002 446873.301966289349366 5.83145138625475 85190.267838727202616 446874.648766305006575 5.83145138625475 85189.690668167197146 446874.240263985935599 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_25">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.501735188256134 446881.382766383409034 5.83145138625475 85186.45495589604252 446880.035966367751826 5.83145138625475 85187.03212645604799 446880.444468686822802 6.5385581674413 85186.078905748261604 446881.791268702480011 6.5385581674413 85185.501735188256134 446881.382766383409034 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_26">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.45495589604252 446880.035966367751826 5.83145138625475 85187.408176603828906 446878.689166352036409 5.83145138625475 85187.985347163834376 446879.097668671107385 6.5385581674413 85187.03212645604799 446880.444468686822802 6.5385581674413 85186.45495589604252 446880.035966367751826 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_27">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.408176603828906 446878.689166352036409 5.83145138625475 85188.361397311615292 446877.3423663363792 5.83145138625475 85188.938567871620762 446877.750868655450176 6.5385581674413 85187.985347163834376 446879.097668671107385 6.5385581674413 85187.408176603828906 446878.689166352036409 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_28">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.361397311629844 446877.3423663363792 5.83145138625475 85189.31461801941623 446875.995566320663784 5.83145138625475 85189.891788579407148 446876.40406863973476 6.5385581674413 85188.938567871620762 446877.750868655450176 6.5385581674413 85188.361397311629844 446877.3423663363792 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_29">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.31461801941623 446875.995566320663784 5.83145138625475 85190.267838727202616 446874.648766305006575 5.83145138625475 85190.845009287193534 446875.057268624077551 6.5385581674413 85189.891788579407148 446876.40406863973476 6.5385581674413 85189.31461801941623 446875.995566320663784 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_30">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85190.267838727202616 446874.648766305006575 5.83145138625475 85191.221059434989002 446873.301966289349366 5.83145138625475 85191.79822999497992 446873.710468608362135 6.5385581674413 85190.845009287193534 446875.057268624077551 6.5385581674413 85190.267838727202616 446874.648766305006575 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_31">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.078905748261604 446881.791268702480011 6.5385581674413 85187.03212645604799 446880.444468686822802 6.5385581674413 85187.609297016038909 446880.85297100583557 7.245664948627841 85186.656076308252523 446882.199771021550987 7.245664948627841 85186.078905748261604 446881.791268702480011 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_32">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.03212645604799 446880.444468686822802 6.5385581674413 85187.985347163834376 446879.097668671107385 6.5385581674413 85188.562517723825295 446879.506170990178362 7.245664948627841 85187.609297016038909 446880.85297100583557 7.245664948627841 85187.03212645604799 446880.444468686822802 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_33">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.985347163834376 446879.097668671107385 6.5385581674413 85188.938567871620762 446877.750868655450176 6.5385581674413 85189.51573843161168 446878.159370974521153 7.245664948627841 85188.562517723825295 446879.506170990178362 7.245664948627841 85187.985347163834376 446879.097668671107385 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_34">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.938567871620762 446877.750868655450176 6.5385581674413 85189.891788579407148 446876.40406863973476 6.5385581674413 85190.468959139398066 446876.812570958805736 7.245664948627841 85189.51573843161168 446878.159370974462945 7.245664948627841 85188.938567871620762 446877.750868655450176 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_35">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.891788579407148 446876.40406863973476 6.5385581674413 85190.845009287193534 446875.057268624077551 6.5385581674413 85191.422179847184452 446875.46577094309032 7.245664948627841 85190.468959139398066 446876.812570958805736 7.245664948627841 85189.891788579407148 446876.40406863973476 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_36">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85190.845009287193534 446875.057268624077551 6.5385581674413 85191.79822999497992 446873.710468608362135 6.5385581674413 85192.375400554970838 446874.118970927433111 7.245664948627841 85191.422179847184452 446875.46577094309032 7.245664948627841 85190.845009287193534 446875.057268624077551 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</nrg3:lod3MultiSurface>
					<nrg3:cellType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CellTypeValue.xml">unknown</nrg3:cellType>
				</nrg3:PhotovoltaicCollector>
			</nrg3:device>
			<nrg3:device>
				<nrg3:EVChargingStation gml:id="id_ev_charging_station_1">
					<gml:description>EVHUB AC Mode 3 laadpaal, 3.7-22 kW (32A, 1/3-phase), Type 2 connector with 8m cable. IP55, polycarbonate housing (410x280x150 mm), built-in DC detection. Dedicated to Golf GTE 2015 (8.7 kWh gross / 7.5 kWh net); car-side limit 3.6 kW. ~150 charges/year.</gml:description>
					<gml:name>EVHUB Laadpaal Type 2</gml:name>
					<core:creationDate>2026-04-04</core:creationDate>
					<nrg3:identifier codeSpace="https://www.elektramat.nl/evhub-laadpaal-type-2-32a-3-7-22kw-met-laadkabel-8-meter-zwart-lp-h8t5oiugl5/">LP-H8T5OIUGL5</nrg3:identifier>
					<nrg3:validFrom>2022-07-18T00:00:00</nrg3:validFrom>
					<nrg3:resource>
						<nrg3:Energy gml:id="id_ev_energy_1">
							<gml:description>Annual electricity consumption for EV charging (Golf GTE 2015, ~150 charges/year x 7.5 kWh net)</gml:description>
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
					<nrg3:installedPower uom="W">22000</nrg3:installedPower>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingStationTypeValue.xml">AC</nrg3:type>
					<nrg3:chargingSpeedLevel codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingSpeedLevelValue.xml">Level 2</nrg3:chargingSpeedLevel>
					<nrg3:connectorType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingConnectorTypeValue.xml">AC - Mennekes (Type2)</nrg3:connectorType>
					<nrg3:hasLoadManagement>true</nrg3:hasLoadManagement>
					<nrg3:access codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/EVChargingAccessTypeValue.xml">private</nrg3:access>
				</nrg3:EVChargingStation>
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
			<bldg:lod0FootPrint>
				<gml:MultiSurface gml:id="id_building_1_lod0" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
					<gml:surfaceMember>
						<gml:Polygon gml:id="id_building_1_lod0_poly_1">
							<gml:exterior>
								<gml:LinearRing>
									<gml:posList>85193.084999046332086 446869.67499871540349 0.105 85199.805115794646554 446874.431276699993759 0.105 85192.183388321878738 446885.199971290887333 0.105 85185.463272527253139 446880.443694590881933 0.105 85193.084999046332086 446869.67499871540349 0.105</gml:posList>
								</gml:LinearRing>
							</gml:exterior>
						</gml:Polygon>
					</gml:surfaceMember>
				</gml:MultiSurface>
			</bldg:lod0FootPrint>
			<bldg:lod1Solid>
				<gml:Solid gml:id="id_building_1_lod1" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
					<gml:exterior>
						<gml:CompositeSurface gml:id="id_building_1_lod1_shell">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.084999046332086 446869.67499871540349 -0.38699999999994 85185.463272527253139 446880.443694590881933 -0.38699999999994 85192.183388321878738 446885.199971290887333 -0.38699999999994 85199.805115794646554 446874.431276699993759 -0.38699999999994 85193.084999046332086 446869.67499871540349 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_2">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85199.805115794646554 446874.431276699993759 -0.38699999999994 85199.805115794646554 446874.431276699993759 9.25110000001437 85193.084999046332086 446869.67499871540349 9.25110000001437 85193.084999046332086 446869.67499871540349 -0.38699999999994 85199.805115794646554 446874.431276699993759 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_3">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.183388321878738 446885.199971290887333 -0.38699999999994 85192.183388321878738 446885.199971290887333 9.25110000001437 85199.805115794646554 446874.431276699993759 9.25110000001437 85199.805115794646554 446874.431276699993759 -0.38699999999994 85192.183388321878738 446885.199971290887333 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_4">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.463272527253139 446880.443694590881933 -0.38699999999994 85185.463272527253139 446880.443694590881933 9.25110000001437 85192.183388321878738 446885.199971290887333 9.25110000001437 85192.183388321878738 446885.199971290887333 -0.38699999999994 85185.463272527253139 446880.443694590881933 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_5">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.084999046332086 446869.67499871540349 -0.38699999999994 85193.084999046332086 446869.67499871540349 9.25110000001437 85185.463272527253139 446880.443694590881933 9.25110000001437 85185.463272527253139 446880.443694590881933 -0.38699999999994 85193.084999046332086 446869.67499871540349 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_6">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.084999046332086 446869.67499871540349 9.25110000001437 85199.805115794646554 446874.431276699993759 9.25110000001437 85192.183388321878738 446885.199971290887333 9.25110000001437 85185.463272527253139 446880.443694590881933 9.25110000001437 85193.084999046332086 446869.67499871540349 9.25110000001437</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:CompositeSurface>
					</gml:exterior>
				</gml:Solid>
			</bldg:lod1Solid>
			<bldg:boundedBy>
				<bldg:GroundSurface gml:id="id_building_1_GroundSurface_1">
					<bldg:lod2MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_GroundSurface_1_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_GroundSurface_1_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.084999046332086 446869.67499871540349 -0.38699999999994 85185.463272527253139 446880.443694590881933 -0.38699999999994 85192.183388321878738 446885.199971290887333 -0.38699999999994 85199.805115794646554 446874.431276699993759 -0.38699999999994 85193.084999046332086 446869.67499871540349 -0.38699999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:GroundSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_1">
					<bldg:lod2MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_1_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_1_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085000000006403 446869.674999999988358 5.15756737011163 85185.463272527253139 446880.443694590881933 5.15756737011165 85185.463272527253139 446880.443694590881933 -0.38699999999994 85193.084999046332086 446869.67499871540349 -0.38699999999994 85193.085000000006403 446869.674999999988358 5.15756737011163</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_2">
					<bldg:lod2MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_2_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_2_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.183388321878738 446885.199971290887333 5.11164310860733 85192.183388321878738 446885.199971290887333 -0.38699999999994 85185.463272527253139 446880.443694590881933 -0.38699999999994 85185.463272527253139 446880.443694590881933 5.15756737011165 85188.80455276738212 446882.808542733371723 9.251100000014391 85192.183388321878738 446885.199971290887333 5.11164310860733</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_3">
					<bldg:lod2MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_3_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_3_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.183388321878738 446885.199971290887333 5.11164310860733 85199.805115794646554 446874.431276699993759 5.111643108607351 85199.805115794646554 446874.431276699993759 -0.38699999999994 85192.183388321878738 446885.199971290887333 -0.38699999999994 85192.183388321878738 446885.199971290887333 5.11164310860733</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_4">
					<bldg:lod2MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_4_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_4_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085000000006403 446869.674999999988358 5.15756737011163 85193.084999046332086 446869.67499871540349 -0.38699999999994 85199.805115794646554 446874.431276699993759 -0.38699999999994 85199.805115794646554 446874.431276699993759 5.111643108607351 85196.426280240135384 446872.039848142478149 9.251100000014391 85193.085000000006403 446869.674999999988358 5.15756737011163</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface_1">
					<bldg:lod2MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_RoofSurface_1_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_RoofSurface_1_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.183388321878738 446885.199971290887333 5.11164310860733 85188.80455276738212 446882.808542733371723 9.251100000014391 85196.426280240135384 446872.039848142478149 9.251100000014391 85199.805115794646554 446874.431276699993759 5.111643108607351 85192.183388321878738 446885.199971290887333 5.11164310860733</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface_2">
					<bldg:lod2MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_RoofSurface_2_lod2" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_RoofSurface_2_lod2_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085000000006403 446869.674999999988358 5.15756737011163 85196.426280240135384 446872.039848142478149 9.251100000014391 85188.80455276738212 446882.808542733371723 9.251100000014391 85185.463272527253139 446880.443694590881933 5.15756737011165 85193.085000000006403 446869.674999999988358 5.15756737011163</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod2MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_5">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_5_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_5_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.084999046332086 446869.67499871540349 0.105000000000045 85193.084999046332086 446869.67499871540349 -0.386999999999924 85199.805114840972237 446874.431275415408891 -0.38699999999994 85199.805114840972237 446874.431275415408891 0.105000000000028 85193.084999046332086 446869.67499871540349 0.105000000000045</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_6">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_6_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_6_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85199.805115794646554 446874.431276699993759 0.105000000000031 85199.805115794646554 446874.431276699993759 -0.386999999999924 85192.183388321878738 446885.199971290887333 -0.386999999999924 85192.183388321878738 446885.199971290887333 0.105000000000031 85199.805115794646554 446874.431276699993759 0.105000000000031</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_7">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_7_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_7_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.183388321878738 446885.199971290887333 0.105000000000031 85192.183388321878738 446885.199971290887333 -0.386999999999924 85185.463272527253139 446880.443694590881933 -0.386999999999924 85185.463272527253139 446880.443694590881933 0.105000000000038 85192.183388321878738 446885.199971290887333 0.105000000000031</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_8">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_8_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_8_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.463272527253139 446880.443694590881933 0.105000000000007 85185.463272527253139 446880.443694590881933 -0.38699999999994 85193.085000000006403 446869.674999999988358 -0.38699999999994 85193.085000000006403 446869.674999999988358 0.105 85185.463272527253139 446880.443694590881933 0.105000000000007</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface_3">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_RoofSurface_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_RoofSurface_3_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085000000006403 446869.674999999988358 5.15756737011163 85196.426280240135384 446872.039848142478149 9.251100000014361 85188.80455276738212 446882.808542733371723 9.251100000014391 85185.463272527253139 446880.443694590881933 5.15756737011165 85193.085000000006403 446869.674999999988358 5.15756737011163</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface_4">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_RoofSurface_4_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_RoofSurface_4_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.183388321878738 446885.199971290887333 5.11164310860733 85188.80455276738212 446882.808542733371723 9.251100000014391 85196.426280240135384 446872.039848142478149 9.2511000000144 85199.805115794646554 446874.431276699993759 5.111643108607341 85192.183388321878738 446885.199971290887333 5.11164310860733</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_9">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_9_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_9_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.183388321878738 446885.199971290887333 0.105000000000031 85185.463272527253139 446880.443694590881933 0.105000000000038 85185.463272527253139 446880.443694590881933 5.15756737011165 85188.80455276738212 446882.808542733371723 9.25110000001437 85192.183388321878738 446885.199971290887333 5.111643108607341 85192.183388321878738 446885.199971290887333 0.105000000000031</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85186.004841219619266 446880.826999080192763 0.179000000000903 85188.188289729892858 446882.372372045880184 0.179000000000903 85188.188289729892858 446882.372372045880184 2.77000000000476 85186.004841219619266 446880.826999080192763 2.77000000000476 85186.004841219619266 446880.826999080192763 0.179000000000903</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85186.759865470827208 446881.361380386108067 3.29700000000553 85188.188289729892858 446882.372372045880184 3.29700000000553 85188.188289729892858 446882.372372045880184 5.510000000008811 85186.759865470827208 446881.361380386108067 5.510000000008811 85186.759865470827208 446881.361380386108067 3.29700000000553</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85189.420815804856829 446883.244713420863263 3.29700000000553 85190.84924006392248 446884.25570508063538 3.29700000000553 85190.84924006392248 446884.25570508063538 5.510000000008811 85189.420815804856829 446883.244713420863263 5.510000000008811 85189.420815804856829 446883.244713420863263 3.29700000000553</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85189.420815804856829 446883.244713420863263 0.179000000000903 85191.604264315130422 446884.790086386550684 0.179000000000903 85191.604264315130422 446884.790086386550684 2.77000000000476 85189.420815804856829 446883.244713420863263 2.77000000000476 85189.420815804856829 446883.244713420863263 0.179000000000903</gml:posList>
										</gml:LinearRing>
									</gml:interior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
					<bldg:opening>
						<bldg:Window gml:id="id_building_1_Window_7">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Window_7_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Window_7_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85188.188289028053987 446882.372372045880184 3.29700000000553 85186.759864768988336 446881.361380386108067 3.29700000000553 85186.759864768988336 446881.361380386108067 5.510000000008811 85188.188289028053987 446882.372372045880184 5.510000000008811 85188.188289028053987 446882.372372045880184 3.29700000000553</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening>
						<bldg:Window gml:id="id_building_1_Window_8">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Window_8_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Window_8_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85190.849238735085237 446884.255703344941139 3.29700000000553 85189.420814476019586 446883.244711685169023 3.29700000000553 85189.420814476019586 446883.244711685169023 5.510000000008811 85190.849238735085237 446884.255703344941139 5.510000000008811 85190.849238735085237 446884.255703344941139 3.29700000000553</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening>
						<bldg:Door gml:id="id_building_1_Door_4">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Door_4_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Door_4_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85191.604269568080781 446884.790085773449391 0.179000000000903 85189.420821057807188 446883.244712807761971 0.179000000000903 85189.420821057807188 446883.244712807761971 2.77000000000476 85191.604269568080781 446884.790085773449391 2.77000000000476 85191.604269568080781 446884.790085773449391 0.179000000000903</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Door>
					</bldg:opening>
					<bldg:opening>
						<bldg:Door gml:id="id_building_1_Door_5">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Door_5_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Door_5_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85188.188289729892858 446882.372371485515032 0.179000000000903 85186.004841219619266 446880.826998519885819 0.179000000000903 85186.004841219619266 446880.826998519885819 2.77000000000476 85188.188289729892858 446882.372371485515032 2.77000000000476 85188.188289729892858 446882.372371485515032 0.179000000000903</gml:posList>
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
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_10">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_10_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_10_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85199.805115794646554 446874.431276699993759 0.105000000000045 85199.805115794646554 446874.431276699993759 5.111643108607341 85196.426280240135384 446872.039848142478149 9.251100000014361 85193.085000000006403 446869.674999999988358 5.15756737011163 85193.085000000006403 446869.674999999988358 0.105000000000028 85199.805115794646554 446874.431276699993759 0.105000000000045</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85198.524047782149864 446873.524578939832281 4.160000000006811 85197.862891410812153 446873.056634228734765 4.1600000000068 85197.862891410812153 446873.056634228734765 5.4400000000087 85198.524047782149864 446873.524578939832281 5.4400000000087 85198.524047782149864 446873.524578939832281 4.160000000006811</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85197.67678813591192 446872.924916458199732 4.1600000000068 85197.015607277295203 446872.456954415829387 4.1600000000068 85197.015607277295203 446872.456954415829387 5.4400000000087 85197.67678813591192 446872.924916458199732 5.4400000000087 85197.67678813591192 446872.924916458199732 4.1600000000068</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85195.836953202961013 446871.622741869126912 4.1600000000068 85195.175796831637854 446871.154797158029396 4.1600000000068 85195.175796831637854 446871.154797158029396 5.4400000000087 85195.836953202961013 446871.622741869126912 5.4400000000087 85195.836953202961013 446871.622741869126912 4.1600000000068</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85194.98969355673762 446871.023079387494363 4.1600000000068 85194.32853718539991 446870.555134676396847 4.16000000000679 85194.32853718539991 446870.555134676396847 5.44000000000869 85194.98969355673762 446871.023079387494363 5.44000000000869 85194.98969355673762 446871.023079387494363 4.1600000000068</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85199.466807793127373 446874.191833435266744 1.18000000000238 85197.915947169007268 446873.094185347552411 1.18000000000238 85197.915947169007268 446873.094185347552411 2.38000000000416 85199.466807793127373 446874.191833435266744 2.38000000000416 85199.466807793127373 446874.191833435266744 1.18000000000238</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85194.936637798542506 446870.985528268734924 1.18000000000237 85193.385777174422401 446869.887880180962384 1.18000000000237 85193.385777174422401 446869.887880180962384 2.38000000000415 85194.936637798542506 446870.985528268734924 2.38000000000415 85194.936637798542506 446870.985528268734924 1.18000000000237</gml:posList>
										</gml:LinearRing>
									</gml:interior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
					<bldg:opening>
						<bldg:Window gml:id="id_building_1_Window_1">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Window_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Window_1_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85197.915946922308649 446873.09418373106746 1.18000000000238 85199.466807546428754 446874.191831818840001 1.18000000000238 85199.466807546428754 446874.191831818840001 2.38000000000416 85197.915946922308649 446873.09418373106746 2.38000000000416 85197.915946922308649 446873.09418373106746 1.18000000000238</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening>
						<bldg:Window gml:id="id_building_1_Window_2">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Window_2_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Window_2_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85193.385777216157294 446869.887881859496702 1.18000000000237 85194.936637840277399 446870.985529947269242 1.18000000000237 85194.936637840277399 446870.985529947269242 2.38000000000415 85193.385777216157294 446869.887881859496702 2.38000000000415 85193.385777216157294 446869.887881859496702 1.18000000000237</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening>
						<bldg:Window gml:id="id_building_1_Window_3">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Window_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Window_3_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85197.862892395758536 446873.056634228734765 4.160000000006811 85198.524048767096247 446873.524578939832281 4.1600000000068 85198.524048767096247 446873.524578939832281 5.4400000000087 85197.862892395758536 446873.056634228734765 5.4400000000087 85197.862892395758536 446873.056634228734765 4.160000000006811</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening>
						<bldg:Window gml:id="id_building_1_Window_4">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Window_4_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Window_4_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85197.015607433320838 446872.456955575849861 4.1600000000068 85197.676788291937555 446872.924917618220206 4.1600000000068 85197.676788291937555 446872.924917618220206 5.4400000000087 85197.015607433320838 446872.456955575849861 5.4400000000087 85197.015607433320838 446872.456955575849861 4.1600000000068</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening>
						<bldg:Window gml:id="id_building_1_Window_5">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Window_5_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Window_5_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85195.175796470648493 446871.154795694339555 4.1600000000068 85195.836952841986204 446871.622740405437071 4.1600000000068 85195.836952841986204 446871.622740405437071 5.4400000000087 85195.175796470648493 446871.154795694339555 5.4400000000087 85195.175796470648493 446871.154795694339555 4.1600000000068</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Window>
					</bldg:opening>
					<bldg:opening>
						<bldg:Window gml:id="id_building_1_Window_6">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Window_6_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Window_6_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85194.328536949164118 446870.555132913577836 4.1600000000068 85194.989693320501829 446871.023077624675352 4.16000000000679 85194.989693320501829 446871.023077624675352 5.44000000000869 85194.328536949164118 446870.555132913577836 5.44000000000869 85194.328536949164118 446870.555132913577836 4.1600000000068</gml:posList>
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
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_11">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_11_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_11_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85199.805115794646554 446874.431276699993759 0.105000000000031 85192.183388321878738 446885.199971290887333 0.105000000000031 85192.183388321878738 446885.199971290887333 5.11164310860733 85199.805115794646554 446874.431276699993759 5.11164310860733 85199.805115794646554 446874.431276699993759 0.105000000000031</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85197.944018799273181 446877.060809862741735 0.120000000000017 85197.944018799273181 446877.060809862741735 2.52300000000358 85197.31778167973971 446877.945616660930682 2.52300000000358 85197.31778167973971 446877.945616660930682 0.120000000000017 85197.944018799273181 446877.060809862741735 0.120000000000017</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85196.534985280319233 446879.051625158637762 0.131000000000027 85196.534985280319233 446879.051625158637762 2.52920000000359 85195.622204238912673 446880.341288203955628 2.52920000000359 85195.622204238912673 446880.341288203955628 0.131000000000027 85196.534985280319233 446879.051625158637762 0.131000000000027</gml:posList>
										</gml:LinearRing>
									</gml:interior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
					<bldg:opening>
						<bldg:Door gml:id="id_building_1_Door_1">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Door_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Door_1_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85196.534985280319233 446879.051625158637762 0.131000000000027 85195.622204238912673 446880.341288203955628 0.131000000000027 85195.622204238912673 446880.341288203955628 2.52920000000359 85196.534985280319233 446879.051625158637762 2.52920000000359 85196.534985280319233 446879.051625158637762 0.131000000000027</gml:posList>
												</gml:LinearRing>
											</gml:exterior>
										</gml:Polygon>
									</gml:surfaceMember>
								</gml:MultiSurface>
							</bldg:lod3MultiSurface>
						</bldg:Door>
					</bldg:opening>
					<bldg:opening>
						<bldg:Door gml:id="id_building_1_Door_2">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Door_2_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Door_2_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85197.944018799273181 446877.060809862741735 0.120000000000017 85197.31778167973971 446877.945616660930682 0.120000000000017 85197.31778167973971 446877.945616660930682 2.52300000000358 85197.944018799273181 446877.060809862741735 2.52300000000358 85197.944018799273181 446877.060809862741735 0.120000000000017</gml:posList>
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
			<bldg:boundedBy>
				<bldg:WallSurface gml:id="id_building_1_WallSurface_12">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_WallSurface_12_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_WallSurface_12_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085000000006403 446869.674999999988358 0.105 85193.085000000006403 446869.674999999988358 5.15756737011163 85185.463272527253139 446880.443694590881933 5.15756737011165 85185.463272527253139 446880.443694590881933 0.105000000000038 85193.085000000006403 446869.674999999988358 0.105</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>85188.814860083875828 446875.708255949022714 0.17900000000012 85188.814860083875828 446875.708255949022714 2.49700000000356 85189.929839457225171 446874.132908051891718 2.49700000000356 85189.929839457225171 446874.132908051891718 0.17900000000012 85188.814860083875828 446875.708255949022714 0.17900000000012</gml:posList>
										</gml:LinearRing>
									</gml:interior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
					<bldg:opening>
						<bldg:Door gml:id="id_building_1_Door_3">
							<bldg:lod3MultiSurface>
								<gml:MultiSurface gml:id="id_building_1_Door_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember>
										<gml:Polygon gml:id="id_building_1_Door_3_lod3_poly_1">
											<gml:exterior>
												<gml:LinearRing>
													<gml:posList>85188.814860083875828 446875.708255949022714 0.17900000000012 85189.929839457225171 446874.132908051891718 0.17900000000012 85189.929839457225171 446874.132908051891718 2.49700000000356 85188.814860083875828 446875.708255949022714 2.49700000000356 85188.814860083875828 446875.708255949022714 0.17900000000012</gml:posList>
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
			<bldg:boundedBy>
				<bldg:GroundSurface gml:id="id_building_1_GroundSurface_2">
					<bldg:lod3MultiSurface>
						<gml:MultiSurface gml:id="id_building_1_GroundSurface_2_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_GroundSurface_2_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.463272527253139 446880.443694590881933 -0.386999999999924 85192.183388321878738 446885.199971290887333 -0.386999999999924 85199.805115794646554 446874.431276699993759 -0.386999999999924 85193.085000000006403 446869.674999999988358 -0.386999999999924 85185.463272527253139 446880.443694590881933 -0.386999999999924</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:GroundSurface>
			</bldg:boundedBy>
			<nrg3:bdgVolume>
				<nrg3:QualifiedVolume>
					<nrg3:description>Building's gross volume of 3D model</nrg3:description>
					<nrg3:source>3D model</nrg3:source>
					<nrg3:value uom="m3">823.30</nrg3:value>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/VolumeTypeValue.xml">grossVolume</nrg3:type>
				</nrg3:QualifiedVolume>
			</nrg3:bdgVolume>
			<nrg3:bdgOwnerName>Han Solo</nrg3:bdgOwnerName>
			<nrg3:bdgOwnershipType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/OwnershipTypeValue.xml">occupantPrivateOwner</nrg3:bdgOwnershipType>
			<nrg3:bdgNumberOfBuildingUnits>1</nrg3:bdgNumberOfBuildingUnits>
			<nrg3:bdgIsProtected>false</nrg3:bdgIsProtected>
			<nrg3:bdgType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/BuildingTypeValue.xml">singleFamilyHouse</nrg3:bdgType>
			<nrg3:occupiedBy>
				<nrg3:Occupants gml:id="id_occupants_1">
					<gml:description>Residents of Han Solo's house</gml:description>
					<gml:name>Occupants 1</gml:name>
					<nrg3:creationDate>2026-04-04</nrg3:creationDate>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/OccupantsTypeValue.xml">residents</nrg3:type>
					<nrg3:numberOfOccupants>6</nrg3:numberOfOccupants>
					<nrg3:averageDietType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/DietTypeValue.xml">omnivorous</nrg3:averageDietType>
					<nrg3:heatDissipation uom="W">80</nrg3:heatDissipation>
					<nrg3:heatDissipationConvectiveFraction uom="unit interval">0.3</nrg3:heatDissipationConvectiveFraction>
					<nrg3:heatDissipationLatentFraction uom="unit interval">0.2</nrg3:heatDissipationLatentFraction>
					<nrg3:heatDissipationRadiantFraction uom="unit interval">0.5</nrg3:heatDissipationRadiantFraction>
				</nrg3:Occupants>
			</nrg3:occupiedBy>
			<nrg3:zone>
				<nrg3:Zone gml:id="zone_1">
					<gml:description>Residential thermal zone with three storeys</gml:description>
					<gml:name>Building zone</gml:name>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CurrentUseValue.xml">residential</nrg3:type>
					<nrg3:coincidesWithLod2Hull>false</nrg3:coincidesWithLod2Hull>
					<nrg3:coincidesWithLod3Hull>true</nrg3:coincidesWithLod3Hull>
					<nrg3:zonePart>
						<nrg3:ZonePart gml:id="zone_part_1">
							<gml:description>Ground floor, heated and cooled year-round at 22 °C</gml:description>
							<gml:name>Ground floor</gml:name>
							<nrg3:lod3Solid>
								<gml:Solid gml:id="zone_part_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:exterior>
										<gml:CompositeSurface gml:id="zone_part_1_lod3_shell">
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_1">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85197.915946922308649 446873.09418373106746 1.18000000000238 85199.466807546428754 446874.191831818840001 1.18000000000238 85199.466807546428754 446874.191831818840001 2.38000000000416 85197.915946922308649 446873.09418373106746 2.38000000000416 85197.915946922308649 446873.09418373106746 1.18000000000238</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_2">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.385777216157294 446869.887881859496702 1.18000000000237 85194.936637840277399 446870.985529947269242 1.18000000000237 85194.936637840277399 446870.985529947269242 2.38000000000415 85193.385777216157294 446869.887881859496702 2.38000000000415 85193.385777216157294 446869.887881859496702 1.18000000000237</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_3">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85192.183388321878738 446885.199971290887333 3.21300000000006 85192.183388321878738 446885.199971290887333 0.105000000000031 85185.463272527253139 446880.443694590881933 0.105000000000038 85185.463272527253139 446880.443694590881933 3.21300000000007 85192.183388321878738 446885.199971290887333 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85186.004841219619266 446880.826999080192763 0.179000000000903 85188.188289729892858 446882.372372045880184 0.179000000000903 85188.188289729892858 446882.372372045880184 2.77000000000476 85186.004841219619266 446880.826999080192763 2.77000000000476 85186.004841219619266 446880.826999080192763 0.179000000000903</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85189.420815804856829 446883.244713420863263 0.179000000000903 85191.604264315130422 446884.790086386550684 0.179000000000903 85191.604264315130422 446884.790086386550684 2.77000000000476 85189.420815804856829 446883.244713420863263 2.77000000000476 85189.420815804856829 446883.244713420863263 0.179000000000903</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_4">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.085000000006403 446869.674999999988358 3.21300000000006 85193.085000000006403 446869.674999999988358 0.105000000000028 85199.805115794646554 446874.431276699993759 0.105000000000045 85199.805115794646554 446874.431276699993759 3.21300000000006 85193.085000000006403 446869.674999999988358 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85199.466807793127373 446874.191833435266744 1.18000000000238 85197.915947169007268 446873.094185347552411 1.18000000000238 85197.915947169007268 446873.094185347552411 2.38000000000416 85199.466807793127373 446874.191833435266744 2.38000000000416 85199.466807793127373 446874.191833435266744 1.18000000000238</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85194.936637798542506 446870.985528268734924 1.18000000000237 85193.385777174422401 446869.887880180962384 1.18000000000237 85193.385777174422401 446869.887880180962384 2.38000000000415 85194.936637798542506 446870.985528268734924 2.38000000000415 85194.936637798542506 446870.985528268734924 1.18000000000237</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_5">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85199.805115794646554 446874.431276699993759 3.21300000000006 85199.805115794646554 446874.431276699993759 0.105000000000031 85192.183388321878738 446885.199971290887333 0.105000000000031 85192.183388321878738 446885.199971290887333 3.21300000000006 85199.805115794646554 446874.431276699993759 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85197.944018799273181 446877.060809862741735 0.120000000000017 85197.944018799273181 446877.060809862741735 2.52300000000358 85197.31778167973971 446877.945616660930682 2.52300000000358 85197.31778167973971 446877.945616660930682 0.120000000000017 85197.944018799273181 446877.060809862741735 0.120000000000017</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85196.534985280319233 446879.051625158637762 0.131000000000027 85196.534985280319233 446879.051625158637762 2.52920000000359 85195.622204238912673 446880.341288203955628 2.52920000000359 85195.622204238912673 446880.341288203955628 0.131000000000027 85196.534985280319233 446879.051625158637762 0.131000000000027</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_6">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85185.463272527253139 446880.443694590881933 3.21300000000006 85185.463272527253139 446880.443694590881933 0.105000000000038 85193.085000000006403 446869.674999999988358 0.105 85193.085000000006403 446869.674999999988358 3.21300000000006 85185.463272527253139 446880.443694590881933 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85188.814860083875828 446875.708255949022714 0.17900000000012 85188.814860083875828 446875.708255949022714 2.49700000000356 85189.929839457225171 446874.132908051891718 2.49700000000356 85189.929839457225171 446874.132908051891718 0.17900000000012 85188.814860083875828 446875.708255949022714 0.17900000000012</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_7">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.084999046332086 446869.67499871540349 3.21300000000006 85199.805115794646554 446874.431276699993759 3.21300000000006 85192.183388321878738 446885.199971290887333 3.21300000000006 85185.463272527253139 446880.443694590881933 3.21300000000006 85193.084999046332086 446869.67499871540349 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_8">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.084999046332086 446869.67499871540349 -0.38699999999994 85185.463272527253139 446880.443694590881933 -0.38699999999994 85192.183388321878738 446885.199971290887333 -0.38699999999994 85199.805115794646554 446874.431276699993759 -0.38699999999994 85193.084999046332086 446869.67499871540349 -0.38699999999994</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_9">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.604269568080781 446884.790085773449391 0.179000000000903 85189.420821057807188 446883.244712807761971 0.179000000000903 85189.420821057807188 446883.244712807761971 2.77000000000476 85191.604269568080781 446884.790085773449391 2.77000000000476 85191.604269568080781 446884.790085773449391 0.179000000000903</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_10">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85188.188289729892858 446882.372371485515032 0.179000000000903 85186.004841219619266 446880.826998519885819 0.179000000000903 85186.004841219619266 446880.826998519885819 2.77000000000476 85188.188289729892858 446882.372371485515032 2.77000000000476 85188.188289729892858 446882.372371485515032 0.179000000000903</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_11">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.084999046332086 446869.67499871540349 0.105000000000045 85193.084999046332086 446869.67499871540349 -0.386999999999924 85199.805114840972237 446874.431275415408891 -0.38699999999994 85199.805114840972237 446874.431275415408891 0.105000000000028 85193.084999046332086 446869.67499871540349 0.105000000000045</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_12">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85196.534985280319233 446879.051625158637762 0.131000000000027 85195.622204238912673 446880.341288203955628 0.131000000000027 85195.622204238912673 446880.341288203955628 2.52920000000359 85196.534985280319233 446879.051625158637762 2.52920000000359 85196.534985280319233 446879.051625158637762 0.131000000000027</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_13">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85197.944018799273181 446877.060809862741735 0.120000000000017 85197.31778167973971 446877.945616660930682 0.120000000000017 85197.31778167973971 446877.945616660930682 2.52300000000358 85197.944018799273181 446877.060809862741735 2.52300000000358 85197.944018799273181 446877.060809862741735 0.120000000000017</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_14">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85199.805115794646554 446874.431276699993759 0.105000000000031 85199.805115794646554 446874.431276699993759 -0.386999999999924 85192.183388321878738 446885.199971290887333 -0.386999999999924 85192.183388321878738 446885.199971290887333 0.105000000000031 85199.805115794646554 446874.431276699993759 0.105000000000031</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_15">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85192.183388321878738 446885.199971290887333 0.105000000000031 85192.183388321878738 446885.199971290887333 -0.386999999999924 85185.463272527253139 446880.443694590881933 -0.386999999999924 85185.463272527253139 446880.443694590881933 0.105000000000038 85192.183388321878738 446885.199971290887333 0.105000000000031</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_16">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85185.463272527253139 446880.443694590881933 0.105000000000007 85185.463272527253139 446880.443694590881933 -0.38699999999994 85193.085000000006403 446869.674999999988358 -0.38699999999994 85193.085000000006403 446869.674999999988358 0.105 85185.463272527253139 446880.443694590881933 0.105000000000007</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_17">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85188.814860083875828 446875.708255949022714 0.17900000000012 85189.929839457225171 446874.132908051891718 0.17900000000012 85189.929839457225171 446874.132908051891718 2.49700000000356 85188.814860083875828 446875.708255949022714 2.49700000000356 85188.814860083875828 446875.708255949022714 0.17900000000012</gml:posList>
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
							<nrg3:heatingSchedule>
								<nrg3:ConstantValueSchedule gml:id="zone_part_1_heating_schedule">
									<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ScheduleTypeValue.xml">typicalYear</nrg3:type>
									<nrg3:value uom="°C">22</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:heatingSchedule>
							<nrg3:coolingSchedule>
								<nrg3:ConstantValueSchedule gml:id="zone_part_1_cooling_schedule">
									<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ScheduleTypeValue.xml">typicalYear</nrg3:type>
									<nrg3:value uom="°C">24</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:coolingSchedule>
						</nrg3:ZonePart>
					</nrg3:zonePart>
					<nrg3:zonePart>
						<nrg3:ZonePart gml:id="zone_part_2">
							<gml:description>First floor, heated to 18 °C when cold outside</gml:description>
							<gml:name>First floor</gml:name>
							<nrg3:lod3Solid>
								<gml:Solid gml:id="zone_part_2_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:exterior>
										<gml:CompositeSurface gml:id="zone_part_2_lod3_shell">
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_1">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85197.862892395758536 446873.056634228734765 4.160000000006811 85198.524048767096247 446873.524578939832281 4.1600000000068 85198.524048767096247 446873.524578939832281 5.4400000000087 85197.862892395758536 446873.056634228734765 5.4400000000087 85197.862892395758536 446873.056634228734765 4.160000000006811</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_2">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85197.015607433320838 446872.456955575849861 4.1600000000068 85197.676788291937555 446872.924917618220206 4.1600000000068 85197.676788291937555 446872.924917618220206 5.4400000000087 85197.015607433320838 446872.456955575849861 5.4400000000087 85197.015607433320838 446872.456955575849861 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_3">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85195.175796470648493 446871.154795694339555 4.1600000000068 85195.836952841986204 446871.622740405437071 4.1600000000068 85195.836952841986204 446871.622740405437071 5.4400000000087 85195.175796470648493 446871.154795694339555 5.4400000000087 85195.175796470648493 446871.154795694339555 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_4">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85194.328536949164118 446870.555132913577836 4.1600000000068 85194.989693320501829 446871.023077624675352 4.16000000000679 85194.989693320501829 446871.023077624675352 5.44000000000869 85194.328536949164118 446870.555132913577836 5.44000000000869 85194.328536949164118 446870.555132913577836 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_5">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85188.188289028053987 446882.372372045880184 3.29700000000553 85186.759864768988336 446881.361380386108067 3.29700000000553 85186.759864768988336 446881.361380386108067 5.510000000008811 85188.188289028053987 446882.372372045880184 5.510000000008811 85188.188289028053987 446882.372372045880184 3.29700000000553</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_6">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85190.849238735085237 446884.255703344941139 3.29700000000553 85189.420814476019586 446883.244711685169023 3.29700000000553 85189.420814476019586 446883.244711685169023 5.510000000008811 85190.849238735085237 446884.255703344941139 5.510000000008811 85190.849238735085237 446884.255703344941139 3.29700000000553</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_7">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.317054767816444 446884.586808925261721 6.17300000000006 85186.29210309687187 446881.030313578841742 6.17300000000006 85193.913830821635202 446870.261618631891906 6.17300000000006 85198.938782277633436 446873.81811428203946 6.17300000000006 85191.317054767816444 446884.586808925261721 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_8">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.913830569639686 446870.261618987948168 6.173000000000091 85186.29210309687187 446881.030313578841742 6.17300000000006 85185.463272527253139 446880.443694590881933 5.15756737011165 85193.085000000006403 446869.674999999988358 5.15756737011163 85193.913830569639686 446870.261618987948168 6.173000000000091</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_9">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.317054767816444 446884.586808925261721 6.17300000000006 85198.938782240569708 446873.818114334426355 6.173000000000051 85199.805115794646554 446874.431276699993759 5.111643108607341 85192.183388321878738 446885.199971290887333 5.11164310860733 85191.317054767816444 446884.586808925261721 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_10">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85192.183388321878738 446885.199971290887333 3.21300000000006 85185.463272527253139 446880.443694590881933 3.21300000000007 85185.463272527253139 446880.443694590881933 5.15756737011165 85186.29210309687187 446881.030313578841742 6.17300000000006 85191.317054767816444 446884.586808925261721 6.17300000000006 85192.183388321878738 446885.199971290887333 5.111643108607341 85192.183388321878738 446885.199971290887333 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85186.759865470827208 446881.361380386108067 3.29700000000553 85188.188289729892858 446882.372372045880184 3.29700000000553 85188.188289729892858 446882.372372045880184 5.510000000008811 85186.759865470827208 446881.361380386108067 5.510000000008811 85186.759865470827208 446881.361380386108067 3.29700000000553</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85189.420815804856829 446883.244713420863263 3.29700000000553 85190.84924006392248 446884.25570508063538 3.29700000000553 85190.84924006392248 446884.25570508063538 5.510000000008811 85189.420815804856829 446883.244713420863263 5.510000000008811 85189.420815804856829 446883.244713420863263 3.29700000000553</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_11">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.085000000006403 446869.674999999988358 3.21300000000006 85199.805115794646554 446874.431276699993759 3.21300000000006 85199.805115794646554 446874.431276699993759 5.111643108607341 85198.938782240569708 446873.818114334426355 6.17300000000006 85193.913830569639686 446870.261618987948168 6.173000000000091 85193.085000000006403 446869.674999999988358 5.15756737011163 85193.085000000006403 446869.674999999988358 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85198.524047782149864 446873.524578939832281 4.160000000006811 85197.862891410812153 446873.056634228734765 4.1600000000068 85197.862891410812153 446873.056634228734765 5.4400000000087 85198.524047782149864 446873.524578939832281 5.4400000000087 85198.524047782149864 446873.524578939832281 4.160000000006811</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85197.67678813591192 446872.924916458199732 4.1600000000068 85197.015607277295203 446872.456954415829387 4.1600000000068 85197.015607277295203 446872.456954415829387 5.4400000000087 85197.67678813591192 446872.924916458199732 5.4400000000087 85197.67678813591192 446872.924916458199732 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85195.836953202961013 446871.622741869126912 4.1600000000068 85195.175796831637854 446871.154797158029396 4.1600000000068 85195.175796831637854 446871.154797158029396 5.4400000000087 85195.836953202961013 446871.622741869126912 5.4400000000087 85195.836953202961013 446871.622741869126912 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>85194.98969355673762 446871.023079387494363 4.1600000000068 85194.32853718539991 446870.555134676396847 4.16000000000679 85194.32853718539991 446870.555134676396847 5.44000000000869 85194.98969355673762 446871.023079387494363 5.44000000000869 85194.98969355673762 446871.023079387494363 4.1600000000068</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_12">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85199.805115794646554 446874.431276699993759 3.21300000000006 85192.183388321878738 446885.199971290887333 3.21300000000006 85192.183388321878738 446885.199971290887333 5.11164310860733 85199.805115794646554 446874.431276699993759 5.11164310860733 85199.805115794646554 446874.431276699993759 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_13">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85185.463272527253139 446880.443694590881933 3.21300000000006 85193.085000000006403 446869.674999999988358 3.21300000000006 85193.085000000006403 446869.674999999988358 5.15756737011163 85185.463272527253139 446880.443694590881933 5.15756737011165 85185.463272527253139 446880.443694590881933 3.21300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_14">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.084999046332086 446869.67499871540349 3.21300000000006 85185.463272527253139 446880.443694590881933 3.21300000000006 85192.183388321878738 446885.199971290887333 3.21300000000006 85199.805115794646554 446874.431276699993759 3.21300000000006 85193.084999046332086 446869.67499871540349 3.21300000000006</gml:posList>
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
							<nrg3:heatingSchedule>
								<nrg3:ConstantValueSchedule gml:id="zone_part_2_heating_schedule">
									<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ScheduleTypeValue.xml">typicalYear</nrg3:type>
									<nrg3:value uom="°C">18</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:heatingSchedule>
							<nrg3:coolingSchedule>
								<nrg3:ConstantValueSchedule gml:id="zone_part_2_cooling_schedule">
									<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/ScheduleTypeValue.xml">typicalYear</nrg3:type>
									<nrg3:value uom="°C">24</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:coolingSchedule>
						</nrg3:ZonePart>
					</nrg3:zonePart>
					<nrg3:zonePart>
						<nrg3:ZonePart gml:id="zone_part_3">
							<gml:description>Attic / second floor, not heated or cooled</gml:description>
							<gml:name>Attic</gml:name>
							<nrg3:lod3Solid>
								<gml:Solid gml:id="zone_part_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:exterior>
										<gml:CompositeSurface gml:id="zone_part_3_lod3_shell">
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_3_lod3_poly_1">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.317054767816444 446884.586808925261721 6.17300000000006 85198.938782277633436 446873.81811428203946 6.17300000000006 85193.913830821635202 446870.261618631891906 6.17300000000006 85186.29210309687187 446881.030313578841742 6.17300000000006 85191.317054767816444 446884.586808925261721 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_3_lod3_poly_2">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.913830569639686 446870.261618987948168 6.173000000000091 85196.426280240135384 446872.039848142478149 9.251100000014361 85188.80455276738212 446882.808542733371723 9.251100000014391 85186.29210309687187 446881.030313578841742 6.17300000000006 85193.913830569639686 446870.261618987948168 6.173000000000091</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_3_lod3_poly_3">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.317054767816444 446884.586808925261721 6.17300000000006 85188.80455276738212 446882.808542733371723 9.251100000014391 85196.426280240135384 446872.039848142478149 9.2511000000144 85198.938782240569708 446873.818114334426355 6.173000000000051 85191.317054767816444 446884.586808925261721 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_3_lod3_poly_4">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.317054767816444 446884.586808925261721 6.17300000000006 85186.29210309687187 446881.030313578841742 6.17300000000006 85188.80455276738212 446882.808542733371723 9.25110000001437 85191.317054767816444 446884.586808925261721 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_3_lod3_poly_5">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.913830569639686 446870.261618987948168 6.173000000000091 85198.938782240569708 446873.818114334426355 6.17300000000006 85196.426280240135384 446872.039848142478149 9.251100000014361 85193.913830569639686 446870.261618987948168 6.173000000000091</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
										</gml:CompositeSurface>
									</gml:exterior>
								</gml:Solid>
							</nrg3:lod3Solid>
							<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/CurrentUseValue.xml">residential</nrg3:type>
							<nrg3:isCooled>false</nrg3:isCooled>
							<nrg3:isHeated>false</nrg3:isHeated>
							<nrg3:coincidesWithLod2Hull>false</nrg3:coincidesWithLod2Hull>
							<nrg3:coincidesWithLod3Hull>false</nrg3:coincidesWithLod3Hull>
						</nrg3:ZonePart>
					</nrg3:zonePart>
				</nrg3:Zone>
			</nrg3:zone>
		</bldg:Building>
	</core:cityObjectMember>
</core:CityModel>
