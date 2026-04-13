<?xml version="1.0" encoding="UTF-8"?>
<core:CityModel xmlns:app="http://www.opengis.net/citygml/appearance/2.0" xmlns:bldg="http://www.opengis.net/citygml/building/2.0" xmlns:brid="http://www.opengis.net/citygml/bridge/2.0" xmlns:core="http://www.opengis.net/citygml/2.0" xmlns:dem="http://www.opengis.net/citygml/relief/2.0" xmlns:frn="http://www.opengis.net/citygml/cityfurniture/2.0" xmlns:gen="http://www.opengis.net/citygml/generics/2.0" xmlns:gml="http://www.opengis.net/gml" xmlns:grp="http://www.opengis.net/citygml/cityobjectgroup/2.0" xmlns:luse="http://www.opengis.net/citygml/landuse/2.0" xmlns:nrg3="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0" xmlns:pbase="http://www.opengis.net/citygml/profiles/base/2.0" xmlns:sch="http://www.ascc.net/xml/schematron" xmlns:smil20="http://www.w3.org/2001/SMIL20/" xmlns:smil20lang="http://www.w3.org/2001/SMIL20/Language" xmlns:tex="http://www.opengis.net/citygml/texturedsurface/2.0" xmlns:tran="http://www.opengis.net/citygml/transportation/2.0" xmlns:tun="http://www.opengis.net/citygml/tunnel/2.0" xmlns:veg="http://www.opengis.net/citygml/vegetation/2.0" xmlns:wtr="http://www.opengis.net/citygml/waterbody/2.0" xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
	<gml:description xlink:type="simple">This is a description</gml:description>
	<gml:name>RenoDAT City</gml:name>
	<gml:boundedBy>
		<gml:Envelope srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
			<gml:lowerCorner srsDimension="3">85183.19305294828 446869.6749987154 -0.38699999999994</gml:lowerCorner>
			<gml:upperCorner srsDimension="3">85199.80511579465 446885.1999712909 9.2511000000144</gml:upperCorner>
		</gml:Envelope>
	</gml:boundedBy>
	<core:cityObjectMember xlink:type="simple">
		<bldg:Building gml:id="id_building_1">
			<nrg3:Metadata xlink:type="simple">
				<nrg3:author>Daan Schlosser</nrg3:author>
				<nrg3:acquisitionMethod>measurement</nrg3:acquisitionMethod>
				<nrg3:owner>Han Solo</nrg3:owner>
			</nrg3:Metadata>
			<gml:name>Han solo's house</gml:name>
			<core:creationDate>2026-04-04</core:creationDate>
			<nrg3:identifier codeSpace="https://bagviewer.kadaster.nl/?objectId=0503100000032914">0503100000032914</nrg3:identifier>
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
							<nrg3:relatedTo xlink:type="simple"/>
						</nrg3:CityObjectRelation>
					</nrg3:relatedTo>
					<nrg3:model>PV-16-270 PW</nrg3:model>
					<nrg3:yearOfInstallation>2020</nrg3:yearOfInstallation>
					<nrg3:numberOfDevices>36</nrg3:numberOfDevices>
					<nrg3:installedPower uom="W">9720.0</nrg3:installedPower>
					<nrg3:azimuth uom="deg">235.65</nrg3:azimuth>
					<nrg3:inclination uom="deg">44.51</nrg3:inclination>
					<nrg3:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="pv_panel_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85183.19305294828 446879.7487571072 3.00302426150856 85184.14627365606 446878.4019570915 3.00302426150856 85184.72344421606 446878.8104594106 3.71013104269511 85183.77022350827 446880.15725942625 3.71013104269511 85183.19305294828 446879.7487571072 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_2">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.14627365606 446878.4019570915 3.00302426150856 85185.09949436385 446877.0551570758 3.00302426150856 85185.67666492384 446877.4636593949 3.71013104269511 85184.72344421606 446878.8104594106 3.71013104269511 85184.14627365606 446878.4019570915 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_3">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.09949436385 446877.0551570758 3.00302426150856 85186.05271507164 446875.70835706015 3.00302426150856 85186.62988563163 446876.1168593792 3.71013104269511 85185.67666492384 446877.4636593949 3.71013104269511 85185.09949436385 446877.0551570758 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_4">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.05271507164 446875.70835706015 3.00302426150856 85187.00593577942 446874.36155704444 3.00302426150856 85187.58310633943 446874.7700593635 3.71013104269511 85186.62988563164 446876.1168593792 3.71013104269511 85186.05271507164 446875.70835706015 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_5">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.00593577942 446874.36155704444 3.00302426150856 85187.95915648721 446873.0147570288 3.00302426150856 85188.53632704722 446873.42325934785 3.71013104269511 85187.58310633943 446874.7700593635 3.71013104269511 85187.00593577942 446874.36155704444 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_6">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.95915648721 446873.0147570288 3.00302426150856 85188.912377195 446871.6679570131 3.00302426150856 85189.489547755 446872.07645933214 3.71013104269511 85188.53632704722 446873.42325934785 3.71013104269511 85187.95915648721 446873.0147570288 3.00302426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_7">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85183.77022350827 446880.15725942625 3.71013104269511 85184.72344421606 446878.8104594106 3.71013104269511 85185.30061477606 446879.2189617296 4.41723782388165 85184.34739406827 446880.5657617453 4.41723782388165 85183.77022350827 446880.15725942625 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_8">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.72344421606 446878.8104594106 3.71013104269511 85185.67666492384 446877.4636593949 3.71013104269511 85186.25383548385 446877.87216171395 4.41723782388165 85185.30061477606 446879.2189617296 4.41723782388165 85184.72344421606 446878.8104594106 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_9">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.67666492384 446877.4636593949 3.71013104269511 85186.62988563163 446876.1168593792 3.71013104269511 85187.20705619163 446876.5253616983 4.41723782388165 85186.25383548385 446877.87216171395 4.41723782388165 85185.67666492384 446877.4636593949 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_10">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.62988563164 446876.1168593792 3.71013104269511 85187.58310633943 446874.7700593635 3.71013104269511 85188.16027689942 446875.1785616826 4.41723782388165 85187.20705619163 446876.52536169824 4.41723782388165 85186.62988563164 446876.1168593792 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_11">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.58310633943 446874.7700593635 3.71013104269511 85188.53632704722 446873.42325934785 3.71013104269511 85189.1134976072 446873.83176166686 4.41723782388165 85188.16027689942 446875.1785616826 4.41723782388165 85187.58310633943 446874.7700593635 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_12">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.53632704722 446873.42325934785 3.71013104269511 85189.489547755 446872.07645933214 3.71013104269511 85190.06671831499 446872.4849616512 4.41723782388165 85189.1134976072 446873.83176166686 4.41723782388165 85188.53632704722 446873.42325934785 3.71013104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_13">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.34739406827 446880.5657617453 4.41723782388165 85185.30061477606 446879.2189617296 4.41723782388165 85185.87778533605 446879.6274640487 5.124344605068201 85184.92456462827 446880.9742640644 5.124344605068201 85184.34739406827 446880.5657617453 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_14">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.30061477606 446879.2189617296 4.41723782388165 85186.25383548385 446877.87216171395 4.41723782388165 85186.83100604384 446878.280664033 5.124344605068201 85185.87778533605 446879.6274640487 5.124344605068201 85185.30061477606 446879.2189617296 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_15">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.25383548385 446877.87216171395 4.41723782388165 85187.20705619163 446876.5253616983 4.41723782388165 85187.78422675162 446876.9338640173 5.124344605068201 85186.83100604384 446878.280664033 5.124344605068201 85186.25383548385 446877.87216171395 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_16">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.20705619163 446876.52536169824 4.41723782388165 85188.16027689942 446875.1785616826 4.41723782388165 85188.73744745941 446875.58706400165 5.124344605068201 85187.78422675162 446876.9338640173 5.124344605068201 85187.20705619163 446876.52536169824 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_17">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.16027689942 446875.1785616826 4.41723782388165 85189.1134976072 446873.83176166686 4.41723782388165 85189.6906681672 446874.24026398594 5.124344605068201 85188.73744745941 446875.58706400165 5.124344605068201 85188.16027689942 446875.1785616826 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_18">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.1134976072 446873.83176166686 4.41723782388165 85190.06671831499 446872.4849616512 4.41723782388165 85190.64388887498 446872.8934639703 5.124344605068201 85189.6906681672 446874.24026398594 5.124344605068201 85189.1134976072 446873.83176166686 4.41723782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_19">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85184.92456462827 446880.9742640644 5.124344605068201 85185.87778533605 446879.6274640487 5.124344605068201 85186.45495589604 446880.03596636775 5.83145138625475 85185.50173518826 446881.3827663834 5.83145138625475 85184.92456462827 446880.9742640644 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_20">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.87778533605 446879.6274640487 5.124344605068201 85186.83100604384 446878.280664033 5.124344605068201 85187.40817660383 446878.68916635204 5.83145138625475 85186.45495589604 446880.03596636775 5.83145138625475 85185.87778533605 446879.6274640487 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_21">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.83100604384 446878.280664033 5.124344605068201 85187.78422675162 446876.9338640173 5.124344605068201 85188.36139731162 446877.3423663364 5.83145138625475 85187.40817660383 446878.68916635204 5.83145138625475 85186.83100604384 446878.280664033 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_22">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.78422675162 446876.9338640173 5.124344605068201 85188.73744745941 446875.58706400165 5.124344605068201 85189.31461801942 446875.99556632066 5.83145138625475 85188.36139731163 446877.3423663364 5.83145138625475 85187.78422675162 446876.9338640173 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_23">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.73744745941 446875.58706400165 5.124344605068201 85189.6906681672 446874.24026398594 5.124344605068201 85190.2678387272 446874.648766305 5.83145138625475 85189.31461801942 446875.99556632066 5.83145138625475 85188.73744745941 446875.58706400165 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_24">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.6906681672 446874.24026398594 5.124344605068201 85190.64388887498 446872.8934639703 5.124344605068201 85191.22105943499 446873.30196628935 5.83145138625475 85190.2678387272 446874.648766305 5.83145138625475 85189.6906681672 446874.24026398594 5.124344605068201</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_25">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85185.50173518826 446881.3827663834 5.83145138625475 85186.45495589604 446880.03596636775 5.83145138625475 85187.03212645605 446880.4444686868 6.5385581674413 85186.07890574826 446881.7912687025 6.5385581674413 85185.50173518826 446881.3827663834 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_26">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.45495589604 446880.03596636775 5.83145138625475 85187.40817660383 446878.68916635204 5.83145138625475 85187.98534716383 446879.0976686711 6.5385581674413 85187.03212645605 446880.4444686868 6.5385581674413 85186.45495589604 446880.03596636775 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_27">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.40817660383 446878.68916635204 5.83145138625475 85188.36139731162 446877.3423663364 5.83145138625475 85188.93856787162 446877.75086865545 6.5385581674413 85187.98534716383 446879.0976686711 6.5385581674413 85187.40817660383 446878.68916635204 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_28">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.36139731163 446877.3423663364 5.83145138625475 85189.31461801942 446875.99556632066 5.83145138625475 85189.8917885794 446876.40406863973 6.5385581674413 85188.93856787162 446877.75086865545 6.5385581674413 85188.36139731163 446877.3423663364 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_29">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.31461801942 446875.99556632066 5.83145138625475 85190.2678387272 446874.648766305 5.83145138625475 85190.8450092872 446875.0572686241 6.5385581674413 85189.8917885794 446876.40406863973 6.5385581674413 85189.31461801942 446875.99556632066 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_30">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85190.2678387272 446874.648766305 5.83145138625475 85191.22105943499 446873.30196628935 5.83145138625475 85191.79822999498 446873.71046860836 6.5385581674413 85190.8450092872 446875.0572686241 6.5385581674413 85190.2678387272 446874.648766305 5.83145138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_31">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85186.07890574826 446881.7912687025 6.5385581674413 85187.03212645605 446880.4444686868 6.5385581674413 85187.60929701604 446880.85297100584 7.245664948627841 85186.65607630825 446882.19977102155 7.245664948627841 85186.07890574826 446881.7912687025 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_32">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.03212645605 446880.4444686868 6.5385581674413 85187.98534716383 446879.0976686711 6.5385581674413 85188.56251772383 446879.5061709902 7.245664948627841 85187.60929701604 446880.85297100584 7.245664948627841 85187.03212645605 446880.4444686868 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_33">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85187.98534716383 446879.0976686711 6.5385581674413 85188.93856787162 446877.75086865545 6.5385581674413 85189.51573843161 446878.1593709745 7.245664948627841 85188.56251772383 446879.5061709902 7.245664948627841 85187.98534716383 446879.0976686711 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_34">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85188.93856787162 446877.75086865545 6.5385581674413 85189.8917885794 446876.40406863973 6.5385581674413 85190.4689591394 446876.8125709588 7.245664948627841 85189.51573843161 446878.15937097446 7.245664948627841 85188.93856787162 446877.75086865545 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_35">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85189.8917885794 446876.40406863973 6.5385581674413 85190.8450092872 446875.0572686241 6.5385581674413 85191.42217984718 446875.4657709431 7.245664948627841 85190.4689591394 446876.8125709588 7.245664948627841 85189.8917885794 446876.40406863973 6.5385581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_36">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85190.8450092872 446875.0572686241 6.5385581674413 85191.79822999498 446873.71046860836 6.5385581674413 85192.37540055497 446874.11897092743 7.245664948627841 85191.42217984718 446875.4657709431 7.245664948627841 85190.8450092872 446875.0572686241 6.5385581674413</gml:posList>
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
					<nrg3:heatSource codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/HeatSourceTypeValue.xml">waterSource</nrg3:heatSource>
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
					<nrg3:identifier codeSpace="https://www.elektramat.nl/evhub-laadpaal-type-2-32a-3-7-22kw-met-laadkabel-8-meter-zwart-lp-h8t5oiugl5/">LP-H8T5OIUGL5</nrg3:identifier>
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
			<bldg:roofType codeSpace="https://www.sig3d.org/codelists/standard/building/2.0/_AbstractBuilding_roofType.xml">1030</bldg:roofType>
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
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_5">
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_5_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_5_lod3_poly_1">
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
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_6">
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_6_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_6_lod3_poly_1">
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
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_7">
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_7_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_7_lod3_poly_1">
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
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_8">
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_8_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_8_lod3_poly_1">
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
				<bldg:RoofSurface gml:id="id_building_1_RoofSurface2_3">
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_3_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85193.085 446869.675 5.1575673701116305 85196.42628024014 446872.0398481425 9.251100000014361 85188.80455276738 446882.8085427334 9.251100000014391 85185.46327252725 446880.4436945909 5.15756737011165 85193.085 446869.675 5.1575673701116305</gml:posList>
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
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_RoofSurface2_4_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_RoofSurface2_4_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85192.18338832188 446885.1999712909 5.11164310860733 85188.80455276738 446882.8085427334 9.251100000014391 85196.42628024014 446872.0398481425 9.2511000000144 85199.80511579465 446874.4312767 5.111643108607341 85192.18338832188 446885.1999712909 5.11164310860733</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:RoofSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_9">
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_9_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_9_lod3_poly_1">
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
						<bldg:Window gml:id="id_building_1_Window2_7">
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
					<bldg:opening xlink:type="simple">
						<bldg:Door gml:id="id_building_1_Door2_4">
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_4_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_4_lod3_poly_1">
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
						<bldg:Door gml:id="id_building_1_Door2_5">
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_5_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_5_lod3_poly_1">
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
				</bldg:WallSurface>
			</bldg:boundedBy>
			<bldg:boundedBy xlink:type="simple">
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_10">
					<bldg:lod3MultiSurface xlink:type="simple">
						<gml:MultiSurface gml:id="id_building_1_WallSurface2_10_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
							<gml:surfaceMember xlink:type="simple">
								<gml:Polygon gml:id="id_building_1_WallSurface2_10_lod3_poly_1">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>85199.80511579465 446874.4312767 0.1050000000000453 85199.80511579465 446874.4312767 5.111643108607341 85196.42628024014 446872.0398481425 9.251100000014361 85193.085 446869.675 5.1575673701116305 85193.085 446869.675 0.10500000000002842 85199.80511579465 446874.4312767 0.1050000000000453</gml:posList>
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
				<bldg:WallSurface gml:id="id_building_1_WallSurface2_11">
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
						<bldg:Door gml:id="id_building_1_Door2_1">
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_1_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_1_lod3_poly_1">
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
						<bldg:Door gml:id="id_building_1_Door2_2">
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_2_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_2_lod3_poly_1">
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
						<bldg:Door gml:id="id_building_1_Door2_3">
							<bldg:lod3MultiSurface xlink:type="simple">
								<gml:MultiSurface gml:id="id_building_1_Door2_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:surfaceMember xlink:type="simple">
										<gml:Polygon gml:id="id_building_1_Door2_3_lod3_poly_1">
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
					<nrg3:zonePart xlink:type="simple">
						<nrg3:ZonePart gml:id="zone_part_3">
							<gml:description xlink:type="simple">Attic / second floor, not heated or cooled</gml:description>
							<gml:name>Attic</gml:name>
							<nrg3:lod3Solid xlink:type="simple">
								<gml:Solid gml:id="zone_part_3_lod3" srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
									<gml:exterior xlink:type="simple">
										<gml:CompositeSurface gml:id="zone_part_3_lod3_shell">
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_3_lod3_poly_1">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.31705476782 446884.58680892526 6.17300000000006 85198.93878227763 446873.81811428204 6.17300000000006 85193.91383082164 446870.2616186319 6.17300000000006 85186.29210309687 446881.03031357884 6.17300000000006 85191.31705476782 446884.58680892526 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_3_lod3_poly_2">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.91383056964 446870.26161898795 6.173000000000091 85196.42628024014 446872.0398481425 9.251100000014361 85188.80455276738 446882.8085427334 9.251100000014391 85186.29210309687 446881.03031357884 6.17300000000006 85193.91383056964 446870.26161898795 6.173000000000091</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_3_lod3_poly_3">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.31705476782 446884.58680892526 6.17300000000006 85188.80455276738 446882.8085427334 9.251100000014391 85196.42628024014 446872.0398481425 9.2511000000144 85198.93878224057 446873.8181143344 6.173000000000051 85191.31705476782 446884.58680892526 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_3_lod3_poly_4">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85191.31705476782 446884.58680892526 6.17300000000006 85186.29210309687 446881.03031357884 6.17300000000006 85188.80455276738 446882.8085427334 9.25110000001437 85191.31705476782 446884.58680892526 6.17300000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember xlink:type="simple">
												<gml:Polygon gml:id="zone_part_3_lod3_poly_5">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>85193.91383056964 446870.26161898795 6.173000000000091 85198.93878224057 446873.8181143344 6.17300000000006 85196.42628024014 446872.0398481425 9.251100000014361 85193.91383056964 446870.26161898795 6.173000000000091</gml:posList>
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
			<nrg3:occupiedBy xlink:type="simple">
				<nrg3:Occupants gml:id="id_occupants_1">
					<gml:description xlink:type="simple">Residents of Han Solo's house</gml:description>
					<gml:name>Occupants 1</gml:name>
					<nrg3:creationDate>2026-04-04</nrg3:creationDate>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/OccupantsTypeValue.xml">residents</nrg3:type>
					<nrg3:numberOfOccupants>6</nrg3:numberOfOccupants>
					<nrg3:averageDietType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/DietTypeValue.xml">omnivorous</nrg3:averageDietType>
					<nrg3:heatDissipation uom="W">80.0</nrg3:heatDissipation>
					<nrg3:heatDissipationConvectiveFraction uom="">0.3</nrg3:heatDissipationConvectiveFraction>
					<nrg3:heatDissipationLatentFraction uom="">0.2</nrg3:heatDissipationLatentFraction>
					<nrg3:heatDissipationRadiantFraction uom="">0.5</nrg3:heatDissipationRadiantFraction>
				</nrg3:Occupants>
			</nrg3:occupiedBy>
			<nrg3:bdgType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/BuildingTypeValue.xml">singleFamilyHouse</nrg3:bdgType>
			<nrg3:bdgIsProtected>false</nrg3:bdgIsProtected>
			<nrg3:bdgNumberOfBuildingUnits>1</nrg3:bdgNumberOfBuildingUnits>
			<nrg3:bdgOwnershipType codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/OwnershipTypeValue.xml">occupantPrivateOwner</nrg3:bdgOwnershipType>
			<nrg3:bdgOwnerName>Han Solo</nrg3:bdgOwnerName>
			<nrg3:bdgVolume>
				<nrg3:QualifiedVolume>
					<nrg3:description>Building's gross volume of 3D model</nrg3:description>
					<nrg3:source>3D model</nrg3:source>
					<nrg3:value uom="m3">823.3</nrg3:value>
					<nrg3:type codeSpace="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0/VolumeTypeValue.xml">grossVolume</nrg3:type>
				</nrg3:QualifiedVolume>
			</nrg3:bdgVolume>
		</bldg:Building>
	</core:cityObjectMember>
</core:CityModel>
