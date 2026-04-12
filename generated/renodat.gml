<?xml version='1.0' encoding='UTF-8'?>
<core:CityModel xmlns:app="http://www.opengis.net/citygml/appearance/2.0" xmlns:bldg="http://www.opengis.net/citygml/building/2.0" xmlns:brid="http://www.opengis.net/citygml/bridge/2.0" xmlns:core="http://www.opengis.net/citygml/2.0" xmlns:dem="http://www.opengis.net/citygml/relief/2.0" xmlns:frn="http://www.opengis.net/citygml/cityfurniture/2.0" xmlns:gen="http://www.opengis.net/citygml/generics/2.0" xmlns:gml="http://www.opengis.net/gml" xmlns:grp="http://www.opengis.net/citygml/cityobjectgroup/2.0" xmlns:luse="http://www.opengis.net/citygml/landuse/2.0" xmlns:nrg3="http://3dcities.bk.tudelft.nl/citygml/2.0/energy/3.0" xmlns:pbase="http://www.opengis.net/citygml/profiles/base/2.0" xmlns:sch="http://www.ascc.net/xml/schematron" xmlns:smil20="http://www.w3.org/2001/SMIL20/" xmlns:smil20lang="http://www.w3.org/2001/SMIL20/Language" xmlns:tex="http://www.opengis.net/citygml/texturedsurface/2.0" xmlns:tran="http://www.opengis.net/citygml/transportation/2.0" xmlns:tun="http://www.opengis.net/citygml/tunnel/2.0" xmlns:veg="http://www.opengis.net/citygml/vegetation/2.0" xmlns:wtr="http://www.opengis.net/citygml/waterbody/2.0" xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
	<gml:description>This is a description</gml:description>
	<gml:name>RenoDAT City</gml:name>
	<gml:boundedBy>
		<gml:Envelope srsName="urn:ogc:def:crs,crs:EPSG::28992,crs:EPSG::5109" srsDimension="3">
			<gml:lowerCorner>1.108053 0.999999 -0.492000</gml:lowerCorner>
			<gml:upperCorner>17.720116 16.524971 9.146100</gml:upperCorner>
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
											<gml:posList>1.10805294827372 11.0737571072188 2.89802426150856 2.06127365606019 9.72695709153456 2.89802426150856 2.63844421605563 10.1354594105911 3.60513104269511 1.68522350826919 11.4822594262753 3.60513104269511 1.10805294827372 11.0737571072188 2.89802426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_2">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>2.06127365606019 9.72695709153456 2.89802426150856 3.01449436384664 8.38015707585031 2.89802426150856 3.59166492384207 8.7886593949068 3.60513104269511 2.63844421605563 10.1354594105911 3.60513104269511 2.06127365606019 9.72695709153456 2.89802426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_3">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>3.01449436384664 8.38015707585031 2.89802426150856 3.96771507163308 7.03335706016604 2.89802426150856 4.54488563162852 7.44185937922254 3.60513104269511 3.59166492384207 8.7886593949068 3.60513104269511 3.01449436384664 8.38015707585031 2.89802426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_4">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>3.96771507163731 7.03335706016006 2.89802426150856 4.92093577942376 5.68655704447579 2.89802426150856 5.49810633941922 6.0950593635323 3.60513104269511 4.54488563163275 7.44185937921657 3.60513104269511 3.96771507163731 7.03335706016006 2.89802426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_5">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>4.92093577942376 5.68655704447579 2.89802426150856 5.8741564872102 4.33975702879154 2.89802426150856 6.45132704720567 4.74825934784803 3.60513104269511 5.49810633941922 6.0950593635323 3.60513104269511 4.92093577942376 5.68655704447579 2.89802426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_6">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>5.8741564872102 4.33975702879154 2.89802426150856 6.82737719499664 2.99295701310727 2.89802426150856 7.40454775499211 3.40145933216377 3.60513104269511 6.45132704720567 4.74825934784803 3.60513104269511 5.8741564872102 4.33975702879154 2.89802426150856</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_7">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>1.68522350826919 11.4822594262753 3.60513104269511 2.63844421605563 10.1354594105911 3.60513104269511 3.2156147760511 10.5439617296476 4.31223782388165 2.26239406826463 11.890761745331799 4.31223782388165 1.68522350826919 11.4822594262753 3.60513104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_8">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>2.63844421605563 10.1354594105911 3.60513104269511 3.59166492384207 8.7886593949068 3.60513104269511 4.16883548383754 9.197161713963309 4.31223782388165 3.2156147760511 10.5439617296476 4.31223782388165 2.63844421605563 10.1354594105911 3.60513104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_9">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>3.59166492384207 8.7886593949068 3.60513104269511 4.54488563162852 7.44185937922254 3.60513104269511 5.12205619162398 7.85036169827904 4.31223782388165 4.16883548383754 9.197161713963309 4.31223782388165 3.59166492384207 8.7886593949068 3.60513104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_10">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>4.54488563163275 7.44185937921657 3.60513104269511 5.49810633941922 6.0950593635323 3.60513104269511 6.07527689941466 6.5035616825888 4.31223782388165 5.12205619162819 7.85036169827306 4.31223782388165 4.54488563163275 7.44185937921657 3.60513104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_11">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>5.49810633941922 6.0950593635323 3.60513104269511 6.45132704720567 4.74825934784803 3.60513104269511 7.0284976072011 5.15676166690454 4.31223782388165 6.07527689941466 6.5035616825888 4.31223782388165 5.49810633941922 6.0950593635323 3.60513104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_12">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>6.45132704720567 4.74825934784803 3.60513104269511 7.40454775499211 3.40145933216377 3.60513104269511 7.98171831498755 3.80996165122028 4.31223782388165 7.0284976072011 5.15676166690454 4.31223782388165 6.45132704720567 4.74825934784803 3.60513104269511</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_13">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>2.26239406826463 11.890761745331799 4.31223782388165 3.2156147760511 10.5439617296476 4.31223782388165 3.79278533604653 10.952464048704099 5.0193446050682 2.83956462826006 12.2992640643883 5.0193446050682 2.26239406826463 11.890761745331799 4.31223782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_14">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>3.2156147760511 10.5439617296476 4.31223782388165 4.16883548383754 9.197161713963309 4.31223782388165 4.74600604383298 9.605664033019821 5.0193446050682 3.79278533604653 10.952464048704099 5.0193446050682 3.2156147760511 10.5439617296476 4.31223782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_15">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>4.16883548383754 9.197161713963309 4.31223782388165 5.12205619162398 7.85036169827904 4.31223782388165 5.69922675161942 8.258864017335551 5.0193446050682 4.74600604383298 9.605664033019821 5.0193446050682 4.16883548383754 9.197161713963309 4.31223782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_16">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>5.12205619162819 7.85036169827306 4.31223782388165 6.07527689941466 6.5035616825888 4.31223782388165 6.6524474594101 6.91206400164531 5.0193446050682 5.69922675162366 8.25886401732957 5.0193446050682 5.12205619162819 7.85036169827306 4.31223782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_17">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>6.07527689941466 6.5035616825888 4.31223782388165 7.0284976072011 5.15676166690454 4.31223782388165 7.60566816719654 5.56526398596105 5.0193446050682 6.6524474594101 6.91206400164531 5.0193446050682 6.07527689941466 6.5035616825888 4.31223782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_18">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>7.0284976072011 5.15676166690454 4.31223782388165 7.98171831498755 3.80996165122028 4.31223782388165 8.55888887498298 4.21846397027679 5.0193446050682 7.60566816719654 5.56526398596105 5.0193446050682 7.0284976072011 5.15676166690454 4.31223782388165</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_19">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>2.83956462826006 12.2992640643883 5.0193446050682 3.79278533604653 10.952464048704099 5.0193446050682 4.36995589604197 11.3609663677606 5.72645138625475 3.41673518825553 12.707766383444801 5.72645138625475 2.83956462826006 12.2992640643883 5.0193446050682</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_20">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>3.79278533604653 10.952464048704099 5.0193446050682 4.74600604383298 9.605664033019821 5.0193446050682 5.32317660382841 10.0141663520763 5.72645138625475 4.36995589604197 11.3609663677606 5.72645138625475 3.79278533604653 10.952464048704099 5.0193446050682</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_21">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>4.74600604383298 9.605664033019821 5.0193446050682 5.69922675161942 8.258864017335551 5.0193446050682 6.27639731161486 8.66736633639206 5.72645138625475 5.32317660382841 10.0141663520763 5.72645138625475 4.74600604383298 9.605664033019821 5.0193446050682</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_22">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>5.69922675162366 8.25886401732957 5.0193446050682 6.6524474594101 6.91206400164531 5.0193446050682 7.22961801940556 7.3205663207018 5.72645138625475 6.27639731161909 8.66736633638607 5.72645138625475 5.69922675162366 8.25886401732957 5.0193446050682</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_23">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>6.6524474594101 6.91206400164531 5.0193446050682 7.60566816719654 5.56526398596105 5.0193446050682 8.18283872719201 5.97376630501756 5.72645138625475 7.22961801940556 7.3205663207018 5.72645138625475 6.6524474594101 6.91206400164531 5.0193446050682</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_24">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>7.60566816719654 5.56526398596105 5.0193446050682 8.55888887498298 4.21846397027679 5.0193446050682 9.136059434978449 4.6269662893333 5.72645138625475 8.18283872719201 5.97376630501756 5.72645138625475 7.60566816719654 5.56526398596105 5.0193446050682</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_25">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>3.41673518825553 12.707766383444801 5.72645138625475 4.36995589604197 11.3609663677606 5.72645138625475 4.94712645603741 11.769468686817101 6.4335581674413 3.99390574825097 13.1162687025013 6.4335581674413 3.41673518825553 12.707766383444801 5.72645138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_26">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>4.36995589604197 11.3609663677606 5.72645138625475 5.32317660382841 10.0141663520763 5.72645138625475 5.90034716382385 10.422668671132801 6.4335581674413 4.94712645603741 11.769468686817101 6.4335581674413 4.36995589604197 11.3609663677606 5.72645138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_27">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>5.32317660382841 10.0141663520763 5.72645138625475 6.27639731161486 8.66736633639206 5.72645138625475 6.8535678716103 9.075868655448559 6.4335581674413 5.90034716382385 10.422668671132801 6.4335581674413 5.32317660382841 10.0141663520763 5.72645138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_28">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>6.27639731161909 8.66736633638607 5.72645138625475 7.22961801940556 7.3205663207018 5.72645138625475 7.806788579401 7.72906863975831 6.4335581674413 6.85356787161453 9.07586865544258 6.4335581674413 6.27639731161909 8.66736633638607 5.72645138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_29">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>7.22961801940556 7.3205663207018 5.72645138625475 8.18283872719201 5.97376630501756 5.72645138625475 8.76000928718744 6.38226862407406 6.4335581674413 7.806788579401 7.72906863975831 6.4335581674413 7.22961801940556 7.3205663207018 5.72645138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_30">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>8.18283872719201 5.97376630501756 5.72645138625475 9.136059434978449 4.6269662893333 5.72645138625475 9.71322999497389 5.03546860838979 6.4335581674413 8.76000928718744 6.38226862407406 6.4335581674413 8.18283872719201 5.97376630501756 5.72645138625475</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_31">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>3.99390574825097 13.1162687025013 6.4335581674413 4.94712645603741 11.769468686817101 6.4335581674413 5.52429701603285 12.1779710058736 7.14066494862784 4.5710763082464 13.5247710215579 7.14066494862784 3.99390574825097 13.1162687025013 6.4335581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_32">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>4.94712645603741 11.769468686817101 6.4335581674413 5.90034716382385 10.422668671132801 6.4335581674413 6.47751772381929 10.8311709901893 7.14066494862784 5.52429701603285 12.1779710058736 7.14066494862784 4.94712645603741 11.769468686817101 6.4335581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_33">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>5.90034716382385 10.422668671132801 6.4335581674413 6.8535678716103 9.075868655448559 6.4335581674413 7.43073843160573 9.484370974505071 7.14066494862784 6.47751772381929 10.8311709901893 7.14066494862784 5.90034716382385 10.422668671132801 6.4335581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_34">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>6.85356787161453 9.07586865544258 6.4335581674413 7.806788579401 7.72906863975831 6.4335581674413 8.38395913939644 8.13757095881482 7.14066494862784 7.43073843161 9.48437097449909 7.14066494862784 6.85356787161453 9.07586865544258 6.4335581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_35">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>7.806788579401 7.72906863975831 6.4335581674413 8.76000928718744 6.38226862407406 6.4335581674413 9.337179847182879 6.79077094313057 7.14066494862784 8.38395913939644 8.13757095881482 7.14066494862784 7.806788579401 7.72906863975831 6.4335581674413</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="pv_panel_1_lod3_poly_36">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>8.76000928718744 6.38226862407406 6.4335581674413 9.71322999497389 5.03546860838979 6.4335581674413 10.290400554969301 5.4439709274463 7.14066494862784 9.337179847182879 6.79077094313057 7.14066494862784 8.76000928718744 6.38226862407406 6.4335581674413</gml:posList>
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
					<nrg3:validFrom>2022-07-18</nrg3:validFrom>
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
									<gml:posList>10.9999990463257 0.999998715414252 0 17.720115794633202 5.75627670000627 0 10.0983883218742 16.524971290884402 0 3.37827252724099 11.7686945908782 0 10.9999990463257 0.999998715414252 0</gml:posList>
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
											<gml:posList>10.9999990463257 0.999998715414195 -0.49199999999994 3.37827252724099 11.7686945908782 -0.49199999999994 10.0983883218742 16.524971290884402 -0.49199999999994 17.720115794633202 5.75627670000621 -0.49199999999994 10.9999990463257 0.999998715414195 -0.49199999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_2">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>17.720115794633202 5.75627670000621 -0.49199999999994 17.720115794633202 5.75627670000621 9.14610000001437 10.9999990463257 0.999998715414195 9.14610000001437 10.9999990463257 0.999998715414195 -0.49199999999994 17.720115794633202 5.75627670000621 -0.49199999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_3">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>10.0983883218742 16.524971290884402 -0.49199999999994 10.0983883218742 16.524971290884402 9.14610000001437 17.720115794633202 5.75627670000621 9.14610000001437 17.720115794633202 5.75627670000621 -0.49199999999994 10.0983883218742 16.524971290884402 -0.49199999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_4">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>3.37827252724099 11.7686945908782 -0.49199999999994 3.37827252724099 11.7686945908782 9.14610000001437 10.0983883218742 16.524971290884402 9.14610000001437 10.0983883218742 16.524971290884402 -0.49199999999994 3.37827252724099 11.7686945908782 -0.49199999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_5">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>10.9999990463257 0.999998715414195 -0.49199999999994 10.9999990463257 0.999998715414195 9.14610000001437 3.37827252724099 11.7686945908782 9.14610000001437 3.37827252724099 11.7686945908782 -0.49199999999994 10.9999990463257 0.999998715414195 -0.49199999999994</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
							<gml:surfaceMember>
								<gml:Polygon gml:id="id_building_1_lod1_poly_6">
									<gml:exterior>
										<gml:LinearRing>
											<gml:posList>10.9999990463257 0.999998715414195 9.14610000001437 17.720115794633202 5.75627670000621 9.14610000001437 10.0983883218742 16.524971290884402 9.14610000001437 3.37827252724099 11.7686945908782 9.14610000001437 10.9999990463257 0.999998715414195 9.14610000001437</gml:posList>
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
											<gml:posList>10.9999990463257 0.999998715414195 -0.49199999999994 3.37827252724099 11.7686945908782 -0.49199999999994 10.0983883218742 16.524971290884402 -0.49199999999994 17.720115794633202 5.75627670000621 -0.49199999999994 10.9999990463257 0.999998715414195 -0.49199999999994</gml:posList>
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
											<gml:posList>10.999999999999901 1.00000000000004 5.05256737011163 3.37827252724097 11.7686945908782 5.05256737011165 3.37827252724099 11.7686945908782 -0.49199999999994 10.9999990463257 0.999998715414195 -0.49199999999994 10.999999999999901 1.00000000000004 5.05256737011163</gml:posList>
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
											<gml:posList>10.0983883218743 16.524971290884501 5.00664310860733 10.0983883218742 16.524971290884402 -0.49199999999994 3.37827252724099 11.7686945908782 -0.49199999999994 3.37827252724097 11.7686945908782 5.05256737011165 6.71955276736927 14.1335427333767 9.146100000014391 10.0983883218743 16.524971290884501 5.00664310860733</gml:posList>
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
											<gml:posList>10.0983883218743 16.524971290884501 5.00664310860733 17.720115794633202 5.75627670000628 5.00664310860735 17.720115794633202 5.75627670000621 -0.49199999999994 10.0983883218742 16.524971290884402 -0.49199999999994 10.0983883218743 16.524971290884501 5.00664310860733</gml:posList>
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
											<gml:posList>10.999999999999901 1.00000000000004 5.05256737011163 10.9999990463257 0.999998715414195 -0.49199999999994 17.720115794633202 5.75627670000621 -0.49199999999994 17.720115794633202 5.75627670000628 5.00664310860735 14.341280240128199 3.36484814249854 9.146100000014391 10.999999999999901 1.00000000000004 5.05256737011163</gml:posList>
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
											<gml:posList>10.0983883218743 16.524971290884501 5.00664310860733 6.71955276736927 14.1335427333767 9.146100000014391 14.341280240128199 3.36484814249854 9.146100000014391 17.720115794633202 5.75627670000628 5.00664310860735 10.0983883218743 16.524971290884501 5.00664310860733</gml:posList>
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
											<gml:posList>10.999999999999901 1.00000000000004 5.05256737011163 14.341280240128199 3.36484814249854 9.146100000014391 6.71955276736927 14.1335427333767 9.146100000014391 3.37827252724097 11.7686945908782 5.05256737011165 10.999999999999901 1.00000000000004 5.05256737011163</gml:posList>
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
											<gml:posList>10.9999990463257 0.999998715414252 0 10.9999990463257 0.999998715414252 -0.491999999999924 17.7201148409589 5.75627541542054 -0.49199999999994 17.7201148409589 5.75627541542054 0 10.9999990463257 0.999998715414252 0</gml:posList>
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
											<gml:posList>17.720115794633202 5.75627670000627 0 17.720115794633202 5.75627670000627 -0.491999999999924 10.0983883218742 16.524971290884402 -0.491999999999924 10.0983883218742 16.524971290884402 0 17.720115794633202 5.75627670000627 0</gml:posList>
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
											<gml:posList>10.0983883218742 16.524971290884402 0 10.0983883218742 16.524971290884402 -0.491999999999924 3.37827252724099 11.7686945908782 -0.491999999999924 3.37827252724099 11.7686945908782 0 10.0983883218742 16.524971290884402 0</gml:posList>
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
											<gml:posList>3.37827252724099 11.7686945908782 0 3.37827252724099 11.7686945908782 -0.49199999999994 11 1 -0.49199999999994 11 1 0 3.37827252724099 11.7686945908782 0</gml:posList>
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
											<gml:posList>10.999999999999901 1.00000000000004 5.05256737011163 14.3412802401281 3.36484814249854 9.146100000014361 6.71955276736927 14.1335427333767 9.146100000014391 3.37827252724097 11.7686945908782 5.05256737011165 10.999999999999901 1.00000000000004 5.05256737011163</gml:posList>
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
											<gml:posList>10.0983883218743 16.524971290884501 5.00664310860733 6.71955276736927 14.1335427333767 9.146100000014391 14.341280240128199 3.36484814249854 9.1461000000144 17.720115794633202 5.75627670000628 5.00664310860734 10.0983883218743 16.524971290884501 5.00664310860733</gml:posList>
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
											<gml:posList>10.0983883218742 16.524971290884402 0 3.37827252724099 11.7686945908782 0 3.37827252724102 11.7686945908782 5.05256737011165 6.71955276736927 14.133542733376601 9.14610000001437 10.0983883218743 16.524971290884402 5.00664310860734 10.0983883218742 16.524971290884402 0</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>3.91984121960928 12.151999080217699 0.074000000000903 6.10328972988856 13.6973720458738 0.074000000000903 6.10328972988856 13.6973720458738 2.66500000000476 3.91984121960928 12.151999080217699 2.66500000000476 3.91984121960928 12.151999080217699 0.074000000000903</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>4.67486547082734 12.686380386098801 3.19200000000553 6.10328972988856 13.6973720458738 3.19200000000553 6.10328972988856 13.6973720458738 5.40500000000881 4.67486547082734 12.686380386098801 5.40500000000881 4.67486547082734 12.686380386098801 3.19200000000553</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>7.33581580484989 14.5697134208796 3.19200000000553 8.764240063911069 15.580705080654599 3.19200000000553 8.7642400639111 15.580705080654599 5.40500000000881 7.33581580484989 14.5697134208796 5.40500000000881 7.33581580484989 14.5697134208796 3.19200000000553</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>7.33581580484989 14.5697134208796 0.074000000000903 9.51926431512916 16.115086386535602 0.074000000000903 9.51926431512916 16.115086386535602 2.66500000000476 7.33581580484989 14.5697134208796 2.66500000000476 7.33581580484989 14.5697134208796 0.074000000000903</gml:posList>
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
													<gml:posList>6.10328902804316 13.6973720458738 3.19200000000553 4.67486476898193 12.686380386098801 3.19200000000553 4.67486476898193 12.686380386098801 5.40500000000881 6.10328902804316 13.6973720458738 5.40500000000881 6.10328902804316 13.6973720458738 3.19200000000553</gml:posList>
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
													<gml:posList>8.7642387350744 15.580703344955699 3.19200000000553 7.33581447601321 14.5697116851807 3.19200000000553 7.33581447601319 14.5697116851807 5.40500000000881 8.7642387350744 15.580703344955699 5.40500000000881 8.7642387350744 15.580703344955699 3.19200000000553</gml:posList>
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
													<gml:posList>9.51926956807492 16.1150857734563 0.074000000000903 7.33582105779564 14.5697128078003 0.074000000000903 7.33582105779564 14.5697128078003 2.66500000000476 9.51926956807492 16.1150857734563 2.66500000000476 9.51926956807492 16.1150857734563 0.074000000000903</gml:posList>
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
													<gml:posList>6.10328972988856 13.6973714855535 0.074000000000903 3.91984121960929 12.1519985198975 0.074000000000903 3.91984121960929 12.1519985198975 2.66500000000476 6.10328972988856 13.6973714855535 2.66500000000476 6.10328972988856 13.6973714855535 0.074000000000903</gml:posList>
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
											<gml:posList>17.720115794633202 5.75627670000627 0 17.720115794633202 5.7562767000063 5.00664310860734 14.3412802401281 3.36484814249854 9.146100000014361 10.999999999999901 1.00000000000004 5.05256737011163 11 1 0 17.720115794633202 5.75627670000627 0</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>16.4390477821368 4.84957893985364 4.05500000000681 15.777891410799899 4.38163422875779 4.0550000000068 15.777891410799899 4.38163422875779 5.3350000000087 16.4390477821368 4.84957893985364 5.3350000000087 16.4390477821368 4.84957893985364 4.05500000000681</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>15.5917881359051 4.24991645822709 4.0550000000068 14.9306072772952 3.78195441584563 4.0550000000068 14.930607277295101 3.78195441584563 5.3350000000087 15.591788135905 4.24991645822709 5.3350000000087 15.5917881359051 4.24991645822709 4.0550000000068</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>13.7519532029612 2.94774186915129 4.0550000000068 13.090796831624299 2.47979715805545 4.0550000000068 13.090796831624299 2.47979715805545 5.3350000000087 13.7519532029612 2.94774186915132 5.3350000000087 13.7519532029612 2.94774186915129 4.0550000000068</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>12.9046935567295 2.34807938752476 4.0550000000068 12.243537185392601 1.8801346764289 4.05500000000679 12.243537185392601 1.88013467642891 5.33500000000869 12.9046935567295 2.34807938752478 5.33500000000869 12.9046935567295 2.34807938752476 4.0550000000068</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>17.381807793117201 5.51683343530514 1.07500000000238 15.8309471689936 4.41918534754943 1.07500000000238 15.8309471689936 4.41918534754943 2.27500000000416 17.381807793117101 5.51683343530514 2.27500000000416 17.381807793117201 5.51683343530514 1.07500000000238</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>12.851637798535799 2.31052826873314 1.07500000000237 11.3007771744122 1.21288018097742 1.07500000000237 11.3007771744122 1.21288018097741 2.27500000000415 12.851637798535799 2.31052826873311 2.27500000000415 12.851637798535799 2.31052826873314 1.07500000000237</gml:posList>
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
													<gml:posList>15.8309469223022 4.4191837310791 1.07500000000238 17.381807546425801 5.51683181883481 1.07500000000238 17.381807546425801 5.51683181883481 2.27500000000416 15.830946922302299 4.4191837310791 2.27500000000416 15.8309469223022 4.4191837310791 1.07500000000238</gml:posList>
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
													<gml:posList>11.3007772161474 1.21288185952515 1.07500000000237 12.851637840271 2.31052994728087 1.07500000000237 12.851637840271 2.31052994728088 2.27500000000415 11.3007772161474 1.21288185952518 2.27500000000415 11.3007772161474 1.21288185952515 1.07500000000237</gml:posList>
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
													<gml:posList>15.777892395753 4.38163422875779 4.05500000000681 16.439048767089901 4.84957893985364 4.0550000000068 16.439048767089901 4.84957893985364 5.3350000000087 15.777892395753 4.38163422875779 5.3350000000087 15.777892395753 4.38163422875779 4.05500000000681</gml:posList>
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
													<gml:posList>14.9306074333212 3.78195557584578 4.0550000000068 15.591788291931101 4.24991761822724 4.0550000000068 15.5917882919312 4.24991761822724 5.3350000000087 14.9306074333212 3.78195557584578 5.3350000000087 14.9306074333212 3.78195557584578 4.0550000000068</gml:posList>
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
													<gml:posList>13.090796470642101 2.47979569435122 4.0550000000068 13.751952841979 2.94774040544706 4.0550000000068 13.751952841979 2.94774040544706 5.3350000000087 13.090796470642101 2.4797956943512 5.3350000000087 13.090796470642101 2.47979569435122 4.0550000000068</gml:posList>
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
													<gml:posList>12.243536949157701 1.88013291358949 4.0550000000068 12.9046933204946 2.34807762468536 4.05500000000679 12.9046933204946 2.34807762468534 5.33500000000869 12.243536949157701 1.88013291358948 5.33500000000869 12.243536949157701 1.88013291358949 4.0550000000068</gml:posList>
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
											<gml:posList>17.720115794633202 5.75627670000627 0 10.0983883218742 16.524971290884402 0 10.0983883218743 16.524971290884402 5.00664310860733 17.720115794633202 5.75627670000627 5.00664310860733 17.720115794633202 5.75627670000627 0</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>15.859018799272199 8.385809862753829 0.015000000000017 15.859018799272199 8.385809862753829 2.41800000000358 15.2327816797316 9.270616660938019 2.41800000000358 15.2327816797316 9.270616660938019 0.015000000000017 15.859018799272199 8.385809862753829 0.015000000000017</gml:posList>
										</gml:LinearRing>
									</gml:interior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>14.4499852803058 10.376625158668199 0.026000000000027 14.4499852803058 10.376625158668199 2.42420000000359 13.537204238908901 11.666288203992099 2.42420000000359 13.537204238908901 11.666288203992099 0.026000000000027 14.4499852803058 10.376625158668199 0.026000000000027</gml:posList>
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
													<gml:posList>14.4499852803058 10.376625158668199 0.026000000000027 13.537204238908901 11.666288203992099 0.026000000000027 13.537204238908901 11.666288203992099 2.42420000000359 14.4499852803058 10.376625158668199 2.42420000000359 14.4499852803058 10.376625158668199 0.026000000000027</gml:posList>
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
													<gml:posList>15.859018799272199 8.385809862753829 0.015000000000017 15.2327816797316 9.270616660938019 0.015000000000017 15.2327816797316 9.270616660938019 2.41800000000358 15.859018799272199 8.385809862753829 2.41800000000358 15.859018799272199 8.385809862753829 0.015000000000017</gml:posList>
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
											<gml:posList>11 1 0 10.999999999999901 1.00000000000004 5.05256737011163 3.37827252724102 11.7686945908782 5.05256737011165 3.37827252724099 11.7686945908782 0 11 1 0</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
									<gml:interior>
										<gml:LinearRing>
											<gml:posList>6.72986008387031 7.03325594905753 0.07400000000012 6.72986008387031 7.03325594905753 2.39200000000356 7.84483945722218 5.45790805192149 2.39200000000356 7.84483945722218 5.45790805192149 0.07400000000012 6.72986008387031 7.03325594905753 0.07400000000012</gml:posList>
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
													<gml:posList>6.72986008387031 7.03325594905753 0.07400000000012 7.84483945722218 5.45790805192149 0.07400000000012 7.84483945722218 5.45790805192149 2.39200000000356 6.72986008387031 7.03325594905753 2.39200000000356 6.72986008387031 7.03325594905753 0.07400000000012</gml:posList>
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
											<gml:posList>3.37827252724102 11.7686945908781 -0.491999999999924 10.0983883218742 16.524971290884402 -0.491999999999924 17.720115794633202 5.75627670000628 -0.491999999999924 11 1 -0.491999999999924 3.37827252724102 11.7686945908781 -0.491999999999924</gml:posList>
										</gml:LinearRing>
									</gml:exterior>
								</gml:Polygon>
							</gml:surfaceMember>
						</gml:MultiSurface>
					</bldg:lod3MultiSurface>
				</bldg:GroundSurface>
			</bldg:boundedBy>
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
															<gml:posList>15.8309469223022 4.4191837310791 1.07500000000238 17.381807546425801 5.51683181883481 1.07500000000238 17.381807546425801 5.51683181883481 2.27500000000416 15.830946922302299 4.4191837310791 2.27500000000416 15.8309469223022 4.4191837310791 1.07500000000238</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_2">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>11.3007772161474 1.21288185952515 1.07500000000237 12.851637840271 2.31052994728087 1.07500000000237 12.851637840271 2.31052994728088 2.27500000000415 11.3007772161474 1.21288185952518 2.27500000000415 11.3007772161474 1.21288185952515 1.07500000000237</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_3">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>10.0983883218743 16.524971290884402 3.10800000000006 10.0983883218742 16.524971290884402 0 3.37827252724099 11.7686945908782 0 3.37827252724101 11.7686945908782 3.10800000000007 10.0983883218743 16.524971290884402 3.10800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>3.91984121960928 12.151999080217699 0.074000000000903 6.10328972988856 13.6973720458738 0.074000000000903 6.10328972988856 13.6973720458738 2.66500000000476 3.91984121960928 12.151999080217699 2.66500000000476 3.91984121960928 12.151999080217699 0.074000000000903</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>7.33581580484989 14.5697134208796 0.074000000000903 9.51926431512916 16.115086386535602 0.074000000000903 9.51926431512916 16.115086386535602 2.66500000000476 7.33581580484989 14.5697134208796 2.66500000000476 7.33581580484989 14.5697134208796 0.074000000000903</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_4">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>11 1.00000000000003 3.10800000000006 11 1 0 17.720115794633202 5.75627670000627 0 17.720115794633202 5.75627670000629 3.10800000000006 11 1.00000000000003 3.10800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>17.381807793117201 5.51683343530514 1.07500000000238 15.8309471689936 4.41918534754943 1.07500000000238 15.8309471689936 4.41918534754943 2.27500000000416 17.381807793117101 5.51683343530514 2.27500000000416 17.381807793117201 5.51683343530514 1.07500000000238</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>12.851637798535799 2.31052826873314 1.07500000000237 11.3007771744122 1.21288018097742 1.07500000000237 11.3007771744122 1.21288018097741 2.27500000000415 12.851637798535799 2.31052826873311 2.27500000000415 12.851637798535799 2.31052826873314 1.07500000000237</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_5">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>17.720115794633202 5.75627670000627 3.10800000000006 17.720115794633202 5.75627670000627 0 10.0983883218742 16.524971290884402 0 10.0983883218743 16.524971290884402 3.10800000000006 17.720115794633202 5.75627670000627 3.10800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>15.859018799272199 8.385809862753829 0.015000000000017 15.859018799272199 8.385809862753829 2.41800000000358 15.2327816797316 9.270616660938019 2.41800000000358 15.2327816797316 9.270616660938019 0.015000000000017 15.859018799272199 8.385809862753829 0.015000000000017</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>14.4499852803058 10.376625158668199 0.026000000000027 14.4499852803058 10.376625158668199 2.42420000000359 13.537204238908901 11.666288203992099 2.42420000000359 13.537204238908901 11.666288203992099 0.026000000000027 14.4499852803058 10.376625158668199 0.026000000000027</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_6">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>3.37827252724101 11.7686945908782 3.10800000000006 3.37827252724099 11.7686945908782 0 11 1 0 11 1.00000000000003 3.10800000000006 3.37827252724101 11.7686945908782 3.10800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>6.72986008387031 7.03325594905753 0.07400000000012 6.72986008387031 7.03325594905753 2.39200000000356 7.84483945722218 5.45790805192149 2.39200000000356 7.84483945722218 5.45790805192149 0.07400000000012 6.72986008387031 7.03325594905753 0.07400000000012</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_7">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>10.9999990463257 0.999998715414195 3.10800000000006 17.720115794633202 5.75627670000621 3.10800000000006 10.0983883218742 16.524971290884402 3.10800000000006 3.37827252724099 11.7686945908782 3.10800000000006 10.9999990463257 0.999998715414195 3.10800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_8">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>10.9999990463257 0.999998715414195 -0.49199999999994 3.37827252724099 11.7686945908782 -0.49199999999994 10.0983883218742 16.524971290884402 -0.49199999999994 17.720115794633202 5.75627670000621 -0.49199999999994 10.9999990463257 0.999998715414195 -0.49199999999994</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_9">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>9.51926956807492 16.1150857734563 0.074000000000903 7.33582105779564 14.5697128078003 0.074000000000903 7.33582105779564 14.5697128078003 2.66500000000476 9.51926956807492 16.1150857734563 2.66500000000476 9.51926956807492 16.1150857734563 0.074000000000903</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_10">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>6.10328972988856 13.6973714855535 0.074000000000903 3.91984121960929 12.1519985198975 0.074000000000903 3.91984121960929 12.1519985198975 2.66500000000476 6.10328972988856 13.6973714855535 2.66500000000476 6.10328972988856 13.6973714855535 0.074000000000903</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_11">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>10.9999990463257 0.999998715414252 0 10.9999990463257 0.999998715414252 -0.491999999999924 17.7201148409589 5.75627541542054 -0.49199999999994 17.7201148409589 5.75627541542054 0 10.9999990463257 0.999998715414252 0</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_12">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>14.4499852803058 10.376625158668199 0.026000000000027 13.537204238908901 11.666288203992099 0.026000000000027 13.537204238908901 11.666288203992099 2.42420000000359 14.4499852803058 10.376625158668199 2.42420000000359 14.4499852803058 10.376625158668199 0.026000000000027</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_13">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>15.859018799272199 8.385809862753829 0.015000000000017 15.2327816797316 9.270616660938019 0.015000000000017 15.2327816797316 9.270616660938019 2.41800000000358 15.859018799272199 8.385809862753829 2.41800000000358 15.859018799272199 8.385809862753829 0.015000000000017</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_14">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>17.720115794633202 5.75627670000627 0 17.720115794633202 5.75627670000627 -0.491999999999924 10.0983883218742 16.524971290884402 -0.491999999999924 10.0983883218742 16.524971290884402 0 17.720115794633202 5.75627670000627 0</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_15">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>10.0983883218742 16.524971290884402 0 10.0983883218742 16.524971290884402 -0.491999999999924 3.37827252724099 11.7686945908782 -0.491999999999924 3.37827252724099 11.7686945908782 0 10.0983883218742 16.524971290884402 0</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_16">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>3.37827252724099 11.7686945908782 0 3.37827252724099 11.7686945908782 -0.49199999999994 11 1 -0.49199999999994 11 1 0 3.37827252724099 11.7686945908782 0</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_1_lod3_poly_17">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>6.72986008387031 7.03325594905753 0.07400000000012 7.84483945722218 5.45790805192149 0.07400000000012 7.84483945722218 5.45790805192149 2.39200000000356 6.72986008387031 7.03325594905753 2.39200000000356 6.72986008387031 7.03325594905753 0.07400000000012</gml:posList>
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
									<nrg3:value uom="°C">22</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:heatingSchedule>
							<nrg3:coolingSchedule>
								<nrg3:ConstantValueSchedule gml:id="zone_part_1_cooling_schedule">
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
															<gml:posList>15.777892395753 4.38163422875779 4.05500000000681 16.439048767089901 4.84957893985364 4.0550000000068 16.439048767089901 4.84957893985364 5.3350000000087 15.777892395753 4.38163422875779 5.3350000000087 15.777892395753 4.38163422875779 4.05500000000681</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_2">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>14.9306074333212 3.78195557584578 4.0550000000068 15.591788291931101 4.24991761822724 4.0550000000068 15.5917882919312 4.24991761822724 5.3350000000087 14.9306074333212 3.78195557584578 5.3350000000087 14.9306074333212 3.78195557584578 4.0550000000068</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_3">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>13.090796470642101 2.47979569435122 4.0550000000068 13.751952841979 2.94774040544706 4.0550000000068 13.751952841979 2.94774040544706 5.3350000000087 13.090796470642101 2.4797956943512 5.3350000000087 13.090796470642101 2.47979569435122 4.0550000000068</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_4">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>12.243536949157701 1.88013291358949 4.0550000000068 12.9046933204946 2.34807762468536 4.05500000000679 12.9046933204946 2.34807762468534 5.33500000000869 12.243536949157701 1.88013291358948 5.33500000000869 12.243536949157701 1.88013291358949 4.0550000000068</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_5">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>6.10328902804316 13.6973720458738 3.19200000000553 4.67486476898193 12.686380386098801 3.19200000000553 4.67486476898193 12.686380386098801 5.40500000000881 6.10328902804316 13.6973720458738 5.40500000000881 6.10328902804316 13.6973720458738 3.19200000000553</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_6">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>8.7642387350744 15.580703344955699 3.19200000000553 7.33581447601321 14.5697116851807 3.19200000000553 7.33581447601319 14.5697116851807 5.40500000000881 8.7642387350744 15.580703344955699 5.40500000000881 8.7642387350744 15.580703344955699 3.19200000000553</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_7">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>9.232054767803231 15.9118089252965 6.06800000000006 4.20710309686766 12.355313578860001 6.06800000000006 11.828830821633 1.58661863192346 6.06800000000006 16.853782277620599 5.14311428205879 6.06800000000006 9.232054767803231 15.9118089252965 6.06800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_8">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>11.8288305696266 1.58661898798186 6.06800000000009 4.20710309686764 12.355313578860001 6.06800000000006 3.37827252724097 11.7686945908782 5.05256737011165 10.999999999999901 1.00000000000004 5.05256737011163 11.8288305696266 1.58661898798186 6.06800000000009</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_9">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>9.2320547678032 15.911808925296601 6.06800000000006 16.8537822405622 5.14311433441841 6.06800000000005 17.720115794633202 5.75627670000628 5.00664310860734 10.0983883218743 16.524971290884501 5.00664310860733 9.2320547678032 15.911808925296601 6.06800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_10">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>10.0983883218743 16.524971290884402 3.10800000000006 3.37827252724101 11.7686945908782 3.10800000000007 3.37827252724102 11.7686945908782 5.05256737011165 4.20710309686769 12.355313578860001 6.06800000000006 9.2320547678032 15.9118089252965 6.06800000000006 10.0983883218743 16.524971290884402 5.00664310860734 10.0983883218743 16.524971290884402 3.10800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>4.67486547082734 12.686380386098801 3.19200000000553 6.10328972988856 13.6973720458738 3.19200000000553 6.10328972988856 13.6973720458738 5.40500000000881 4.67486547082734 12.686380386098801 5.40500000000881 4.67486547082734 12.686380386098801 3.19200000000553</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>7.33581580484989 14.5697134208796 3.19200000000553 8.764240063911069 15.580705080654599 3.19200000000553 8.7642400639111 15.580705080654599 5.40500000000881 7.33581580484989 14.5697134208796 5.40500000000881 7.33581580484989 14.5697134208796 3.19200000000553</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_11">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>11 1.00000000000003 3.10800000000006 17.720115794633202 5.75627670000629 3.10800000000006 17.720115794633202 5.7562767000063 5.00664310860734 16.853782240562101 5.14311433441842 6.06800000000006 11.8288305696266 1.58661898798186 6.06800000000009 10.999999999999901 1.00000000000004 5.05256737011163 11 1.00000000000003 3.10800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>16.4390477821368 4.84957893985364 4.05500000000681 15.777891410799899 4.38163422875779 4.0550000000068 15.777891410799899 4.38163422875779 5.3350000000087 16.4390477821368 4.84957893985364 5.3350000000087 16.4390477821368 4.84957893985364 4.05500000000681</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>15.5917881359051 4.24991645822709 4.0550000000068 14.9306072772952 3.78195441584563 4.0550000000068 14.930607277295101 3.78195441584563 5.3350000000087 15.591788135905 4.24991645822709 5.3350000000087 15.5917881359051 4.24991645822709 4.0550000000068</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>13.7519532029612 2.94774186915129 4.0550000000068 13.090796831624299 2.47979715805545 4.0550000000068 13.090796831624299 2.47979715805545 5.3350000000087 13.7519532029612 2.94774186915132 5.3350000000087 13.7519532029612 2.94774186915129 4.0550000000068</gml:posList>
														</gml:LinearRing>
													</gml:interior>
													<gml:interior>
														<gml:LinearRing>
															<gml:posList>12.9046935567295 2.34807938752476 4.0550000000068 12.243537185392601 1.8801346764289 4.05500000000679 12.243537185392601 1.88013467642891 5.33500000000869 12.9046935567295 2.34807938752478 5.33500000000869 12.9046935567295 2.34807938752476 4.0550000000068</gml:posList>
														</gml:LinearRing>
													</gml:interior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_12">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>17.720115794633202 5.75627670000627 3.10800000000006 10.0983883218743 16.524971290884402 3.10800000000006 10.0983883218743 16.524971290884402 5.00664310860733 17.720115794633202 5.75627670000627 5.00664310860733 17.720115794633202 5.75627670000627 3.10800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_13">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>3.37827252724101 11.7686945908782 3.10800000000006 11 1.00000000000003 3.10800000000006 10.999999999999901 1.00000000000004 5.05256737011163 3.37827252724102 11.7686945908782 5.05256737011165 3.37827252724101 11.7686945908782 3.10800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_2_lod3_poly_14">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>10.9999990463257 0.999998715414195 3.10800000000006 3.37827252724099 11.7686945908782 3.10800000000006 10.0983883218742 16.524971290884402 3.10800000000006 17.720115794633202 5.75627670000621 3.10800000000006 10.9999990463257 0.999998715414195 3.10800000000006</gml:posList>
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
									<nrg3:value uom="°C">18</nrg3:value>
								</nrg3:ConstantValueSchedule>
							</nrg3:heatingSchedule>
							<nrg3:coolingSchedule>
								<nrg3:ConstantValueSchedule gml:id="zone_part_2_cooling_schedule">
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
															<gml:posList>9.232054767803231 15.9118089252965 6.06800000000006 16.853782277620599 5.14311428205879 6.06800000000006 11.828830821633 1.58661863192346 6.06800000000006 4.20710309686766 12.355313578860001 6.06800000000006 9.232054767803231 15.9118089252965 6.06800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_3_lod3_poly_2">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>11.8288305696266 1.58661898798186 6.06800000000009 14.3412802401281 3.36484814249854 9.146100000014361 6.71955276736927 14.1335427333767 9.146100000014391 4.20710309686764 12.355313578860001 6.06800000000006 11.8288305696266 1.58661898798186 6.06800000000009</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_3_lod3_poly_3">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>9.2320547678032 15.911808925296601 6.06800000000006 6.71955276736927 14.1335427333767 9.146100000014391 14.341280240128199 3.36484814249854 9.1461000000144 16.8537822405622 5.14311433441841 6.06800000000005 9.2320547678032 15.911808925296601 6.06800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_3_lod3_poly_4">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>9.2320547678032 15.9118089252965 6.06800000000006 4.20710309686769 12.355313578860001 6.06800000000006 6.71955276736927 14.133542733376601 9.14610000001437 9.2320547678032 15.9118089252965 6.06800000000006</gml:posList>
														</gml:LinearRing>
													</gml:exterior>
												</gml:Polygon>
											</gml:surfaceMember>
											<gml:surfaceMember>
												<gml:Polygon gml:id="zone_part_3_lod3_poly_5">
													<gml:exterior>
														<gml:LinearRing>
															<gml:posList>11.8288305696266 1.58661898798186 6.06800000000009 16.853782240562101 5.14311433441842 6.06800000000006 14.3412802401281 3.36484814249854 9.146100000014361 11.8288305696266 1.58661898798186 6.06800000000009</gml:posList>
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
	<app:appearanceMember>
		<app:Appearance gml:id="id_appearance_0b52cc5e-92df-49e8-b1e3-ab39e65957b4">
			<app:theme>Solar Device Appearance</app:theme>
			<app:surfaceDataMember>
				<app:X3DMaterial gml:id="X3DMaterial_0b52cc5e-92df-49e8-b1e3-ab39e65957b4_back">
					<gml:description>This is Colour Black (BACK) for Solar Devices LoD2-3</gml:description>
					<gml:name>Colour Black (BACK) Solar Devices LoD2-3</gml:name>
					<app:isFront>false</app:isFront>
					<app:diffuseColor>0 0 0</app:diffuseColor>
					<app:transparency>0</app:transparency>
					<app:target>#pv_panel_1_lod3</app:target>
				</app:X3DMaterial>
			</app:surfaceDataMember>
			<app:surfaceDataMember>
				<app:X3DMaterial gml:id="X3DMaterial_0b52cc5e-92df-49e8-b1e3-ab39e65957b4_front">
					<gml:description>This is Colour Black (FRONT) for Solar Devices LoD2-3</gml:description>
					<gml:name>Colour Black (FRONT) Solar Devices LoD2-3</gml:name>
					<app:isFront>true</app:isFront>
					<app:diffuseColor>0 0 0</app:diffuseColor>
					<app:transparency>0</app:transparency>
					<app:target>#pv_panel_1_lod3</app:target>
				</app:X3DMaterial>
			</app:surfaceDataMember>
		</app:Appearance>
	</app:appearanceMember>
</core:CityModel>
