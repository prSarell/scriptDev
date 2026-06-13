//Maya ASCII 2025ff03 scene
//Name: exampleRig.ma
//Last modified: Fri, Jun 12, 2026 01:36:26 PM
//Codeset: 1252
requires maya "2025ff03";
requires "stereoCamera" "10.0";
requires -nodeType "aiOptions" -nodeType "aiAOVDriver" -nodeType "aiAOVFilter" -nodeType "aiImagerDenoiserOidn"
		 "mtoa" "5.4.8.2";
currentUnit -l centimeter -a degree -t film;
fileInfo "application" "maya";
fileInfo "product" "Maya 2025";
fileInfo "version" "2025";
fileInfo "cutIdentifier" "202512041342-b90de33065";
fileInfo "osv" "Windows 11 Pro v2009 (Build: 26200)";
fileInfo "UUID" "434055D5-449B-7216-46CB-659523F7B14D";
createNode transform -s -n "persp";
	rename -uid "5D66B147-4C38-9096-AE34-0FA5D99F0628";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 30.537216007836435 16.743310537157509 41.723814573253343 ;
	setAttr ".r" -type "double3" -6.3383527296027857 36.200000000000308 -4.9267520248516717e-16 ;
createNode camera -s -n "perspShape" -p "persp";
	rename -uid "A7A3AE0B-42D1-2FDE-7D10-EDADA330768F";
	setAttr -k off ".v" no;
	setAttr ".fl" 34.999999999999993;
	setAttr ".coi" 52.022916873032045;
	setAttr ".imn" -type "string" "persp";
	setAttr ".den" -type "string" "persp_depth";
	setAttr ".man" -type "string" "persp_mask";
	setAttr ".tp" -type "double3" 0 11 0 ;
	setAttr ".hc" -type "string" "viewSet -p %camera";
createNode transform -s -n "top";
	rename -uid "509D70AF-42BB-17CA-9912-D2A6087A5DE6";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 1000.1 0 ;
	setAttr ".r" -type "double3" -90 0 0 ;
createNode camera -s -n "topShape" -p "top";
	rename -uid "EFE0835F-4F29-89BD-9353-839A61FB5138";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 30;
	setAttr ".imn" -type "string" "top";
	setAttr ".den" -type "string" "top_depth";
	setAttr ".man" -type "string" "top_mask";
	setAttr ".hc" -type "string" "viewSet -t %camera";
	setAttr ".o" yes;
	setAttr ".ai_translator" -type "string" "orthographic";
createNode transform -s -n "front";
	rename -uid "D3EA3FD3-4640-62B4-4CE2-E7914DB7E6A6";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 1.3322676295501878e-15 8.5 1000.1361526551902 ;
createNode camera -s -n "frontShape" -p "front";
	rename -uid "365DF4CA-4270-03B8-61A0-FDA0AFA02E96";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 999.2531203362422;
	setAttr ".ow" 109.98408409286911;
	setAttr ".imn" -type "string" "front";
	setAttr ".den" -type "string" "front_depth";
	setAttr ".man" -type "string" "front_mask";
	setAttr ".tp" -type "double3" 1.3322676295501878e-15 8.5 0.88303231894800316 ;
	setAttr ".hc" -type "string" "viewSet -f %camera";
	setAttr ".o" yes;
	setAttr ".ai_translator" -type "string" "orthographic";
createNode transform -s -n "side";
	rename -uid "644BC310-49CB-A2C7-2D00-708ACF5516BD";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 1000.1 0 0 ;
	setAttr ".r" -type "double3" 0 90 0 ;
createNode camera -s -n "sideShape" -p "side";
	rename -uid "BBB5910E-4596-DB99-F683-2DAD1CABD0B1";
	setAttr -k off ".v" no;
	setAttr ".rnd" no;
	setAttr ".coi" 1000.1;
	setAttr ".ow" 30;
	setAttr ".imn" -type "string" "side";
	setAttr ".den" -type "string" "side_depth";
	setAttr ".man" -type "string" "side_mask";
	setAttr ".hc" -type "string" "viewSet -s %camera";
	setAttr ".o" yes;
	setAttr ".ai_translator" -type "string" "orthographic";
createNode transform -n "hairRIg";
	rename -uid "F09159BD-4245-516B-2F41-7B89AA474F73";
createNode joint -n "hair_000_SKL" -p "hairRIg";
	rename -uid "70FEA874-4096-E0F1-EB1E-2AB366E72B7D";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".jo" -type "double3" 0 0 90 ;
createNode parentConstraint -n "hair_000_SKL_parentConstraint1" -p "hair_000_SKL";
	rename -uid "4A7E61D0-429F-C045-4217-1F9D796F3666";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_000_JNTW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".rsrr" -type "double3" 0 0 90 ;
	setAttr -k on ".w0";
createNode joint -n "hair_001_SKL" -p "hair_000_SKL";
	rename -uid "7176D7F9-4876-6181-F6DE-DC9FF3F0C04A";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode parentConstraint -n "hair_001_SKL_parentConstraint1" -p "hair_001_SKL";
	rename -uid "E74C3D51-4534-8160-C614-C59CF9568825";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_001_JNTW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".rst" -type "double3" 0 2 0 ;
	setAttr ".rsrr" -type "double3" 0 0 90 ;
	setAttr -k on ".w0";
createNode joint -n "hair_002_SKL" -p "hair_001_SKL";
	rename -uid "267ECC36-44EC-C136-6D74-E8A064B48CB7";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode parentConstraint -n "hair_002_SKL_parentConstraint1" -p "hair_002_SKL";
	rename -uid "02240C1D-42C7-080A-18B5-21B5D45D198F";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_002_JNTW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".rst" -type "double3" 0 4 0 ;
	setAttr ".rsrr" -type "double3" 0 0 90 ;
	setAttr -k on ".w0";
createNode joint -n "hair_003_SKL" -p "hair_002_SKL";
	rename -uid "1747C49E-477E-42DD-0E8A-8EAB92F0D9B1";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode parentConstraint -n "hair_003_SKL_parentConstraint1" -p "hair_003_SKL";
	rename -uid "84032778-41C4-3956-46FB-13A8B701CD54";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_003_JNTW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".rst" -type "double3" 0 6 0 ;
	setAttr ".rsrr" -type "double3" 0 0 90 ;
	setAttr -k on ".w0";
createNode joint -n "hair_004_SKL" -p "hair_003_SKL";
	rename -uid "0EF4E3C1-474E-3DF4-E59A-FDB49775A5F8";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".jo" -type "double3" 0 0 -90 ;
createNode parentConstraint -n "hair_004_SKL_parentConstraint1" -p "hair_004_SKL";
	rename -uid "2F266852-41A3-87F0-257F-4B8EC4E9E3B3";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_004_JNTW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".lr" -type "double3" 0 0 90 ;
	setAttr ".rst" -type "double3" 0 8 0 ;
	setAttr ".rsrr" -type "double3" 0 0 90 ;
	setAttr -k on ".w0";
createNode joint -n "hair_005_SKL" -p "hair_004_SKL";
	rename -uid "C7E8AA19-480B-9A12-867A-F399904CAEE7";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode parentConstraint -n "hair_005_SKL_parentConstraint1" -p "hair_005_SKL";
	rename -uid "15306CB1-41B3-37FC-2C4A-21BB26AD5786";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_005_JNTW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".rst" -type "double3" 0 10 0 ;
	setAttr ".rsrr" -type "double3" 0 0 90 ;
	setAttr -k on ".w0";
createNode transform -n "hair_NoTransform000_GRP" -p "hairRIg";
	rename -uid "9F933FE0-4111-8DAF-0B8D-7CBBC29DE511";
createNode transform -n "hair_Controls_GRP" -p "hair_NoTransform000_GRP";
	rename -uid "B59F85E3-4C9B-DAA9-B132-5E9C2B991578";
createNode transform -n "hair_CTL000_GRP" -p "hair_Controls_GRP";
	rename -uid "C9979E1B-4C5F-3D1D-32CB-06ACCBD23904";
createNode transform -n "hairBtm_CTL" -p "hair_CTL000_GRP";
	rename -uid "73040E8D-45BC-6CB6-8C78-11A795ECA844";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
createNode nurbsCurve -n "hairBtm_CTLShape" -p "hairBtm_CTL";
	rename -uid "F2D16176-446F-A2F0-F599-06B4637980DB";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 8 2 no 3
		13 -2 -1 0 1 2 3 4 5 6 7 8 9 10
		11
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		-4.4327767502175526 1.4070942476024109e-32 -2.2979592950099322e-16
		-3.134446499564898 -1.919294936395389e-16 3.134446499564898
		-4.4403427878412899e-16 -2.7142929292443668e-16 4.4327767502175535
		3.134446499564898 -1.9192949363953888e-16 3.1344464995648975
		4.4327767502175526 -3.7014716840440396e-32 6.044962003119836e-16
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		;
createNode transform -n "hair_UpTwist000_NULL" -p "hairBtm_CTL";
	rename -uid "55491DFD-4C34-DDD4-EF30-D1BC355FFB77";
	setAttr ".r" -type "double3" 180 0 90 ;
createNode parentConstraint -n "hair_CTL000_GRP_parentConstraint1" -p "hair_CTL000_GRP";
	rename -uid "A0022924-4A91-D1A1-48BA-CE8DF496A0D4";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_All002_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr -k on ".w0";
createNode transform -n "hair_CTL002_GRP" -p "hair_Controls_GRP";
	rename -uid "244D2E83-4B5D-D0C1-6595-E29B8768D2B4";
createNode transform -n "hairTop_CTL" -p "hair_CTL002_GRP";
	rename -uid "AC101F69-4061-94C6-EBBE-239471136672";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr ".ro" 4;
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
createNode nurbsCurve -n "hairTop_CTLShape" -p "hairTop_CTL";
	rename -uid "9F9B6EE8-4F58-E8B5-756C-86B3F30ED335";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 8 2 no 3
		13 -2 -1 0 1 2 3 4 5 6 7 8 9 10
		11
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		-4.4327767502175526 1.4070942476024109e-32 -2.2979592950099322e-16
		-3.134446499564898 -1.919294936395389e-16 3.134446499564898
		-4.4403427878412899e-16 -2.7142929292443668e-16 4.4327767502175535
		3.134446499564898 -1.9192949363953888e-16 3.1344464995648975
		4.4327767502175526 -3.7014716840440396e-32 6.044962003119836e-16
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		;
createNode transform -n "hair_DwnTwist000_NULL" -p "hairTop_CTL";
	rename -uid "31C07A52-47A8-EF94-6A10-BDBEEAB87F51";
	setAttr ".r" -type "double3" 180 0 90 ;
createNode parentConstraint -n "hair_CTL002_GRP_parentConstraint1" -p "hair_CTL002_GRP";
	rename -uid "C893623A-4046-79BC-F7BE-E9A003D35AB7";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_CTL002constraint_GRPW0" -dv 
		1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".rst" -type "double3" 0 10 0 ;
	setAttr -k on ".w0";
createNode transform -n "hair_All001_GRP" -p "hair_Controls_GRP";
	rename -uid "07C2784B-4952-64F2-2477-14B50A43ED1D";
createNode transform -n "hairCOG_Mid_CTL" -p "hair_All001_GRP";
	rename -uid "56DD640F-4D2E-FF9E-EFB6-EF9A83F19462";
	setAttr -k off ".v";
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
createNode nurbsCurve -n "hairCOG_Mid_CTLShape" -p "hairCOG_Mid_CTL";
	rename -uid "04292BB3-49DE-497D-BF18-53A02FE7DBFE";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 6 0 no 3
		11 0 0 0 1 2 3 4 5 6 6 6
		9
		-2.4120000000000001e-15 4.2230000000000001e-35 7.9372176682272988
		3.8185271911283234 4.2230000000000001e-35 4.5536652958006165
		6.3642119852138777 4.2230000000000001e-35 1.170112923373918
		5.0913695881711041 4.2230000000000001e-35 -3.7346874250304691
		2.4230000000000001e-15 4.2230000000000001e-35 -6.2803722191160229
		-5.091369588171097 4.2230000000000001e-35 -3.7346874250304749
		-6.364211985213875 4.2230000000000001e-35 1.1701129233739136
		-3.8185271911283292 4.2230000000000001e-35 4.553665295800605
		-1.6060000000000001e-15 1.9110000000000001e-32 7.9372176682272988
		;
createNode parentConstraint -n "hair_All001_GRP_parentConstraint1" -p "hair_All001_GRP";
	rename -uid "12CB5557-4DA7-8BBF-C843-2D8063D34FF6";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_All000_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr -k on ".w0";
createNode transform -n "hair_All002_GRP" -p "hair_Controls_GRP";
	rename -uid "1DEC0371-4ED4-5E39-1282-1FAF2A5F308D";
createNode transform -n "hairCOG_Btm_CTL" -p "hair_All002_GRP";
	rename -uid "24001A06-46D3-AE1A-C904-539EE35B4648";
	setAttr -k off ".v";
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
createNode nurbsCurve -n "hairCOG_Btm_CTLShape" -p "hairCOG_Btm_CTL";
	rename -uid "6008FFC6-4579-A823-4628-248648C42BDA";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 6 0 no 3
		11 0 0 0 1 2 3 4 5 6 6 6
		9
		-2.195e-15 8.1199999999999997e-35 7.246874953712628
		3.4846338500471794 8.1199999999999997e-35 4.1591815734589863
		5.80772308341197 8.1199999999999997e-35 1.0714881932053306
		4.6461784667295767 8.1199999999999997e-35 -3.4044347127470127
		2.2169999999999999e-15 8.1199999999999997e-35 -5.7275239461118046
		-4.6461784667295722 8.1199999999999997e-35 -3.404434712747018
		-5.8077230834119673 8.1199999999999997e-35 1.0714881932053264
		-3.4846338500471838 8.1199999999999997e-35 4.1591815734589765
		-1.4600000000000001e-15 1.7480000000000001e-32 7.246874953712628
		;
createNode transform -n "hair_CTL002constraint_GRP" -p "hairCOG_Btm_CTL";
	rename -uid "11B6CB66-4B34-FCB7-BE22-C5B3F53FFD25";
	setAttr ".t" -type "double3" 0 10 0 ;
createNode parentConstraint -n "hair_All002_GRP_parentConstraint1" -p "hair_All002_GRP";
	rename -uid "11F168C6-47A5-96D8-3B4D-329D931222F8";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_All001_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr -k on ".w0";
createNode transform -n "hair_All000_GRP" -p "hair_Controls_GRP";
	rename -uid "D7B19447-45B9-3ED5-707D-83BC87DAB3A5";
createNode transform -n "hairCOG_CTL" -p "hair_All000_GRP";
	rename -uid "4DE8ADF1-42A3-55E0-726B-4B9B17FA6D4F";
	addAttr -ci true -sn "subControlOneVisibility" -ln "subControlOneVisibility" -min 
		0 -max 1 -at "long";
	addAttr -ci true -sn "subControlTwoVisibility" -ln "subControlTwoVisibility" -min 
		0 -max 1 -at "long";
	addAttr -ci true -k true -sn "globalScale" -ln "globalScale" -dv 1 -at "double";
	setAttr -l on -k off ".v";
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
	setAttr -cb on ".subControlOneVisibility";
	setAttr -cb on ".subControlTwoVisibility";
	setAttr -k on ".globalScale";
createNode nurbsCurve -n "hairCOG_CTLShape" -p "hairCOG_CTL";
	rename -uid "6AE22AA3-4335-77B8-545D-BAAD6CD3589A";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 6 0 no 3
		11 0 0 0 1 2 3 4 5 6 6 6
		9
		-2.587e-15 5.4479999999999998e-36 8.4899356232051044
		4.086088758749157 5.4479999999999998e-36 4.8693000688131338
		6.8101479312486024 5.4479999999999998e-36 1.2486645144211457
		5.4481183449988837 5.4479999999999998e-36 -3.9998118128096531
		2.587e-15 5.4479999999999998e-36 -6.7238709853090981
		-5.4481183449988766 5.4479999999999998e-36 -3.9998118128096594
		-6.8101479312485997 5.4479999999999998e-36 1.248664514421141
		-4.0860887587491641 5.4479999999999998e-36 4.8693000688131205
		-1.724e-15 2.041e-32 8.4899356232051044
		;
createNode ikHandle -n "hair_000_IKH" -p "hairCOG_CTL";
	rename -uid "B8BF40E9-44B8-18F3-81FA-DB9D7FD90C9E";
	setAttr ".v" no;
	setAttr ".t" -type "double3" 0 10 0 ;
	setAttr ".r" -type "double3" 0 0 90 ;
	setAttr ".roc" yes;
createNode joint -n "hair_000_FK" -p "hairCOG_CTL";
	rename -uid "7ED81248-483D-A5A3-03EA-468E632EC40C";
	setAttr ".v" no;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".jo" -type "double3" 0 0 90 ;
createNode joint -n "hair_001_FK" -p "hair_000_FK";
	rename -uid "CEE48F99-42C3-362B-7A03-55AF31C38923";
	setAttr ".t" -type "double3" 2 0 0 ;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode joint -n "hair_002_FK" -p "hair_001_FK";
	rename -uid "FE643020-4576-37FF-7314-E7B9D634BFEC";
	setAttr ".t" -type "double3" 2 0 0 ;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode joint -n "hair_003_FK" -p "hair_002_FK";
	rename -uid "D9340F40-4AAD-3109-08AC-B3BB4A940F2E";
	setAttr ".t" -type "double3" 2 0 0 ;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode joint -n "hair_004_FK" -p "hair_003_FK";
	rename -uid "A12A0769-4E40-1521-0029-98984BE36D7F";
	setAttr ".t" -type "double3" 2 0 0 ;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode joint -n "hair_005_FK" -p "hair_004_FK";
	rename -uid "38260878-49B3-4795-7FF7-30A0879BB1ED";
	setAttr ".t" -type "double3" 2 0 0 ;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".jot" -type "string" "none";
createNode joint -n "hair_005_JNT" -p "hair_005_FK";
	rename -uid "D9D1D9CA-4166-D4A5-3EED-E98A4F65600E";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode ikEffector -n "hair_000_EFF" -p "hair_004_FK";
	rename -uid "05FE9DA8-4AE8-8740-0694-07B732FA359E";
	setAttr ".v" no;
	setAttr ".hd" yes;
createNode joint -n "hair_004_JNT" -p "hair_004_FK";
	rename -uid "CF4A8B52-4C2B-C286-D8AC-04A5B2A66BDF";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode joint -n "hair_003_JNT" -p "hair_003_FK";
	rename -uid "3F69764A-49E5-439B-DAEB-DDBD9EF56E9B";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode joint -n "hair_002_JNT" -p "hair_002_FK";
	rename -uid "FC83B905-4816-7A0B-7960-F5832078C17F";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode joint -n "hair_001_JNT" -p "hair_001_FK";
	rename -uid "ABC5700E-40B4-BDBF-9888-33BCF75ABBC2";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode joint -n "hair_000_JNT" -p "hair_000_FK";
	rename -uid "AB006ECD-4A5D-BB6C-EE46-D8859994BD91";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
createNode transform -n "hair_Rig_GRP" -p "hair_NoTransform000_GRP";
	rename -uid "5082915D-4B3F-41F1-AC64-1A825AC60CEA";
createNode transform -n "hair_Joint_000_FOL" -p "hair_Rig_GRP";
	rename -uid "32C0346C-470A-DAA7-7E76-71A748471C7E";
	setAttr ".v" no;
	setAttr -l on ".tx";
	setAttr -l on ".ty";
	setAttr -l on ".tz";
	setAttr -l on ".rx";
	setAttr -l on ".ry";
	setAttr -l on ".rz";
createNode follicle -n "hair_Joint_000_FOLShape" -p "hair_Joint_000_FOL";
	rename -uid "F4626222-4D0C-BA11-BDBA-D49DC4A44A1A";
	setAttr -k off ".v";
	setAttr ".pu" 0.5;
	setAttr -s 2 ".sts[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".cws[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".ats[0:1]"  0 1 3 1 0.2 3;
createNode joint -n "hair_Joint_000_DRV" -p "hair_Joint_000_FOL";
	rename -uid "7B500D69-4A3F-B2B7-E2F0-EAA2146E111D";
	addAttr -ci true -sn "liw" -ln "lockInfluenceWeights" -min 0 -max 1 -at "bool";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".bps" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 1.3202807952317105e-10 0 1;
createNode transform -n "hair_Joint_001_FOL" -p "hair_Rig_GRP";
	rename -uid "4E151B03-438B-777C-8A0A-25813E047F4C";
	setAttr ".v" no;
	setAttr -l on ".tx";
	setAttr -l on ".ty";
	setAttr -l on ".tz";
	setAttr -l on ".rx";
	setAttr -l on ".ry";
	setAttr -l on ".rz";
createNode follicle -n "hair_Joint_001_FOLShape" -p "hair_Joint_001_FOL";
	rename -uid "3B136238-42C2-6F2C-F600-EC809B69D26A";
	setAttr -k off ".v";
	setAttr ".pu" 0.5;
	setAttr ".pv" 0.20000000000000004;
	setAttr -s 2 ".sts[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".cws[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".ats[0:1]"  0 1 3 1 0.2 3;
createNode joint -n "hair_Joint_001_DRV" -p "hair_Joint_001_FOL";
	rename -uid "FC5DE976-4E69-D1BB-AF3B-8EAF0B14E30B";
	addAttr -ci true -sn "liw" -ln "lockInfluenceWeights" -min 0 -max 1 -at "bool";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".bps" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 1.999999998856846 0 1;
createNode transform -n "hair_Joint_002_FOL" -p "hair_Rig_GRP";
	rename -uid "1E3AC690-4FF7-E29A-CDB9-718F06165E13";
	setAttr ".v" no;
	setAttr -l on ".tx";
	setAttr -l on ".ty";
	setAttr -l on ".tz";
	setAttr -l on ".rx";
	setAttr -l on ".ry";
	setAttr -l on ".rz";
createNode follicle -n "hair_Joint_002_FOLShape" -p "hair_Joint_002_FOL";
	rename -uid "CB013064-46C4-286F-36BF-A692C848AEF5";
	setAttr -k off ".v";
	setAttr ".pu" 0.5;
	setAttr ".pv" 0.40000000000000008;
	setAttr -s 2 ".sts[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".cws[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".ats[0:1]"  0 1 3 1 0.2 3;
createNode joint -n "hair_Joint_002_DRV" -p "hair_Joint_002_FOL";
	rename -uid "225922FF-4C8D-16F2-8D6F-AD97AA7040A5";
	addAttr -ci true -sn "liw" -ln "lockInfluenceWeights" -min 0 -max 1 -at "bool";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".bps" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 4.0000000011152945 0 1;
createNode transform -n "hair_Joint_003_FOL" -p "hair_Rig_GRP";
	rename -uid "97522AE0-4A81-22A1-521E-92A60C5446BE";
	setAttr ".v" no;
	setAttr -l on ".tx";
	setAttr -l on ".ty";
	setAttr -l on ".tz";
	setAttr -l on ".rx";
	setAttr -l on ".ry";
	setAttr -l on ".rz";
createNode follicle -n "hair_Joint_003_FOLShape" -p "hair_Joint_003_FOL";
	rename -uid "4AF10264-424A-04D5-6611-36872A4223C6";
	setAttr -k off ".v";
	setAttr ".pu" 0.5;
	setAttr ".pv" 0.6;
	setAttr -s 2 ".sts[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".cws[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".ats[0:1]"  0 1 3 1 0.2 3;
createNode joint -n "hair_Joint_003_DRV" -p "hair_Joint_003_FOL";
	rename -uid "2394F73B-417E-BFC3-7AF7-2E9D061E52CD";
	addAttr -ci true -sn "liw" -ln "lockInfluenceWeights" -min 0 -max 1 -at "bool";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".bps" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 5.9999999988846984 0 1;
createNode transform -n "hair_Joint_004_FOL" -p "hair_Rig_GRP";
	rename -uid "408AE0F8-4290-960A-9457-C0848A5DA22F";
	setAttr ".v" no;
	setAttr -l on ".tx";
	setAttr -l on ".ty";
	setAttr -l on ".tz";
	setAttr -l on ".rx";
	setAttr -l on ".ry";
	setAttr -l on ".rz";
createNode follicle -n "hair_Joint_004_FOLShape" -p "hair_Joint_004_FOL";
	rename -uid "C56EA736-4337-1887-4825-F897FB6C661B";
	setAttr -k off ".v";
	setAttr ".pu" 0.5;
	setAttr ".pv" 0.80000000000000016;
	setAttr -s 2 ".sts[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".cws[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".ats[0:1]"  0 1 3 1 0.2 3;
createNode joint -n "hair_Joint_004_DRV" -p "hair_Joint_004_FOL";
	rename -uid "9B9BCF4E-4037-1229-3184-D1B482A5D2AE";
	addAttr -ci true -sn "liw" -ln "lockInfluenceWeights" -min 0 -max 1 -at "bool";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".bps" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 8.0000000011431567 0 1;
createNode transform -n "hair_Joint_005_FOL" -p "hair_Rig_GRP";
	rename -uid "8678D1A5-4871-B85A-5C4D-43B653B687FC";
	setAttr ".v" no;
	setAttr -l on ".tx";
	setAttr -l on ".ty";
	setAttr -l on ".tz";
	setAttr -l on ".rx";
	setAttr -l on ".ry";
	setAttr -l on ".rz";
createNode follicle -n "hair_Joint_005_FOLShape" -p "hair_Joint_005_FOL";
	rename -uid "DE2965D7-48F6-B046-9DD3-4C964982A20F";
	setAttr -k off ".v";
	setAttr ".pu" 0.5;
	setAttr ".pv" 0.99999999999999989;
	setAttr -s 2 ".sts[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".cws[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".ats[0:1]"  0 1 3 1 0.2 3;
createNode joint -n "hair_Joint_005_DRV" -p "hair_Joint_005_FOL";
	rename -uid "50BD192F-401A-BA67-0D7B-98B351424A2D";
	addAttr -ci true -sn "liw" -ln "lockInfluenceWeights" -min 0 -max 1 -at "bool";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".bps" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 9.9999999998679741 0 1;
createNode transform -n "hair_Mid000_FOL" -p "hair_Rig_GRP";
	rename -uid "5DDDC6A9-4295-D867-A048-8F9DF6DB6673";
createNode follicle -n "hair_Mid000_FOLShape" -p "hair_Mid000_FOL";
	rename -uid "A0DB8165-4EE5-6785-0A5E-B1AAB03C1859";
	setAttr -k off ".v" no;
	setAttr ".pu" 0.5;
	setAttr ".pv" 0.5;
	setAttr -s 2 ".sts[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".cws[0:1]"  0 1 3 1 0.2 3;
	setAttr -s 2 ".ats[0:1]"  0 1 3 1 0.2 3;
createNode transform -n "hair_CTL001_TopSDK_GRP" -p "hair_Mid000_FOL";
	rename -uid "EB2E5D87-4198-8644-7B77-118E1C987EED";
createNode transform -n "hair_CTL001_TopRotateSDK_GRP" -p "hair_CTL001_TopSDK_GRP";
	rename -uid "E11AA198-42F5-998C-79D5-ABAF376F1A51";
createNode transform -n "hair_CTL001_BtmRotateSDK_GRP" -p "hair_CTL001_TopRotateSDK_GRP";
	rename -uid "82EC08EA-4FCD-E517-74BA-75AE388505D1";
	setAttr ".r" -type "double3" 0 0 0 ;
	setAttr -av ".rz";
createNode transform -n "hair_CTL001_BtmSDK_GRP" -p "hair_CTL001_BtmRotateSDK_GRP";
	rename -uid "53374033-44C7-D50D-44DF-A08F092681C0";
	setAttr ".r" -type "double3" 0 0 0 ;
	setAttr -av ".rz";
createNode transform -n "hairMid_CTL" -p "hair_CTL001_BtmSDK_GRP";
	rename -uid "E7826152-4614-93B3-A19B-A58D2CCDB4E2";
	setAttr -l on -k off ".v";
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
createNode nurbsCurve -n "hairMid_CTLShape" -p "hairMid_CTL";
	rename -uid "10E96778-4CA1-DDF7-97B6-B4A5F992E68D";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 8 2 no 3
		13 -2 -1 0 1 2 3 4 5 6 7 8 9 10
		11
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		-4.4327767502175526 1.4070942476024109e-32 -2.2979592950099322e-16
		-3.134446499564898 -1.919294936395389e-16 3.134446499564898
		-4.4403427878412899e-16 -2.7142929292443668e-16 4.4327767502175535
		3.134446499564898 -1.9192949363953888e-16 3.1344464995648975
		4.4327767502175526 -3.7014716840440396e-32 6.044962003119836e-16
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		;
createNode transform -n "hair_Geo000_GRP" -p "hair_Rig_GRP";
	rename -uid "D6BA5949-4404-D474-A080-38A28D9B5FE3";
createNode joint -n "hair_Geo000_FK" -p "hair_Geo000_GRP";
	rename -uid "4DFA3E0D-4B4A-5BA7-BDFF-7EB05660657C";
	addAttr -ci true -sn "liw" -ln "lockInfluenceWeights" -min 0 -max 1 -at "bool";
	setAttr ".v" no;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".bps" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
createNode parentConstraint -n "hair_Geo000_FK_parentConstraint1" -p "hair_Geo000_FK";
	rename -uid "D77ACD87-4AE2-D6DC-3C5E-34A2B6899139";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_000_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr -k on ".w0";
createNode transform -n "hair_Geo001_GRP" -p "hair_Rig_GRP";
	rename -uid "17889179-41CC-1541-17EB-55B317B593B3";
	setAttr ".t" -type "double3" 0 4.9999999999999947 0 ;
createNode joint -n "hair_Geo001_FK" -p "hair_Geo001_GRP";
	rename -uid "C476E2A5-4898-2FB0-BD22-03B55A91591A";
	addAttr -ci true -sn "liw" -ln "lockInfluenceWeights" -min 0 -max 1 -at "bool";
	setAttr ".v" no;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".bps" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 4.9999999999999947 0 1;
createNode parentConstraint -n "hair_Geo001_FK_parentConstraint1" -p "hair_Geo001_FK";
	rename -uid "14F35ED2-4CB5-B59A-0FE4-D9BF62E1D733";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_001_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".rst" -type "double3" 0 4.9999999999999947 0 ;
	setAttr -k on ".w0";
createNode transform -n "hair_Geo002_GRP" -p "hair_Rig_GRP";
	rename -uid "0DEC4DD7-4930-A045-2380-E5A940AA6417";
createNode joint -n "hair_Geo002_FK" -p "hair_Geo002_GRP";
	rename -uid "166F74B5-4127-52E9-7C9F-438B32D62B20";
	addAttr -ci true -sn "liw" -ln "lockInfluenceWeights" -min 0 -max 1 -at "bool";
	setAttr ".v" no;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".bps" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 10 0 1;
createNode parentConstraint -n "hair_Geo002_FK_parentConstraint1" -p "hair_Geo002_FK";
	rename -uid "99F1B7F5-4B70-2CA8-2038-F191E8CD423F";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hair_002_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".rst" -type "double3" 0 10 0 ;
	setAttr -k on ".w0";
createNode transform -n "hair_000_GEO" -p "hair_Rig_GRP";
	rename -uid "FBDE7CBA-4FCF-CA30-22A8-9E9A2C896A3C";
	setAttr ".v" no;
	setAttr -l on ".tx";
	setAttr -l on ".ty";
	setAttr -l on ".tz";
	setAttr -l on ".rx";
	setAttr -l on ".ry";
	setAttr -l on ".rz";
	setAttr -l on ".sx";
	setAttr -l on ".sy";
	setAttr -l on ".sz";
createNode nurbsSurface -n "hair_000_GEOShape" -p "hair_000_GEO";
	rename -uid "161F8D45-4E1D-71BD-D622-91BEA12CC3CB";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".tw" yes;
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".dvu" 0;
	setAttr ".dvv" 0;
	setAttr ".cpr" 4;
	setAttr ".cps" 4;
createNode nurbsSurface -n "hair_000_GEOShapeOrig" -p "hair_000_GEO";
	rename -uid "A79A32A1-417E-1453-96A4-7182ED13D129";
	setAttr -k off ".v";
	setAttr ".io" yes;
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".dvu" 0;
	setAttr ".dvv" 0;
	setAttr ".cpr" 4;
	setAttr ".cps" 4;
	setAttr ".cc" -type "nurbsSurface" 
		3 3 0 0 no 
		6 0 0 0 1 1 1
		10 0 0 0 0.20000000000000004 0.40000000000000008 0.59999999999999998 0.80000000000000016
		 1 1 1
		
		32
		-0.49999999999999967 1.3202807952317105e-10 0
		-0.49999999999999989 0.66666667251667322 -0
		-0.49999999999999994 1.9999999943585707 -0
		-0.5 4.0000000041110679 0
		-0.5 5.9999999958889223 0
		-0.49999999999999956 8.0000000056414375 0
		-0.50000000000000011 9.3333333274833183 -0
		-0.50000000000000011 9.9999999998679723 -0
		-0.16666666666666657 1.3202807952317105e-10 0
		-0.16666666666666666 0.66666667251667322 -0
		-0.16666666666666655 1.9999999943585707 -0
		-0.16666666666666674 4.0000000041110679 0
		-0.16666666666666674 5.9999999958889223 0
		-0.16666666666666655 8.0000000056414375 0
		-0.16666666666666671 9.3333333274833183 -0
		-0.16666666666666671 9.9999999998679723 -0
		0.16666666666666657 1.3202807952317105e-10 0
		0.16666666666666666 0.66666667251667322 -0
		0.16666666666666655 1.9999999943585707 -0
		0.16666666666666674 4.0000000041110679 0
		0.16666666666666674 5.9999999958889223 0
		0.16666666666666655 8.0000000056414375 0
		0.16666666666666671 9.3333333274833183 -0
		0.16666666666666671 9.9999999998679723 -0
		0.49999999999999967 1.3202807952317105e-10 0
		0.49999999999999989 0.66666667251667322 -0
		0.49999999999999994 1.9999999943585707 -0
		0.5 4.0000000041110679 0
		0.5 5.9999999958889223 0
		0.49999999999999956 8.0000000056414375 0
		0.50000000000000011 9.3333333274833183 -0
		0.50000000000000011 9.9999999998679723 -0
		
		;
createNode transform -n "hair_001_GEO" -p "hair_Rig_GRP";
	rename -uid "263C318E-4490-0690-26BA-708ACE920E2A";
	setAttr ".v" no;
	setAttr -l on ".tx";
	setAttr -l on ".ty";
	setAttr -l on ".tz";
	setAttr -l on ".rx";
	setAttr -l on ".ry";
	setAttr -l on ".rz";
	setAttr -l on ".sx";
	setAttr -l on ".sy";
	setAttr -l on ".sz";
createNode nurbsSurface -n "hair_001_GEOShape" -p "hair_001_GEO";
	rename -uid "A391DE38-4E7E-58F9-014D-80A4F8A154EF";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".tw" yes;
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".dvu" 0;
	setAttr ".dvv" 0;
	setAttr ".cpr" 4;
	setAttr ".cps" 4;
createNode nurbsSurface -n "hair_001_GEOShapeOrig" -p "hair_001_GEO";
	rename -uid "0F3A590E-4C17-5327-A754-1EA5BB162885";
	setAttr -k off ".v";
	setAttr ".io" yes;
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
	setAttr ".dvu" 0;
	setAttr ".dvv" 0;
	setAttr ".cpr" 4;
	setAttr ".cps" 4;
	setAttr ".cc" -type "nurbsSurface" 
		3 3 0 0 no 
		6 0 0 0 1 1 1
		10 0 0 0 0.20000000000000004 0.40000000000000008 0.59999999999999998 0.80000000000000016
		 1 1 1
		
		32
		-0.49999999999999967 1.3202807952317105e-10 0
		-0.49999999999999989 0.66666667251667322 -0
		-0.49999999999999994 1.9999999943585707 -0
		-0.5 4.0000000041110679 0
		-0.5 5.9999999958889223 0
		-0.49999999999999956 8.0000000056414375 0
		-0.50000000000000011 9.3333333274833183 -0
		-0.50000000000000011 9.9999999998679723 -0
		-0.16666666666666657 1.3202807952317105e-10 0
		-0.16666666666666666 0.66666667251667322 -0
		-0.16666666666666655 1.9999999943585707 -0
		-0.16666666666666674 4.0000000041110679 0
		-0.16666666666666674 5.9999999958889223 0
		-0.16666666666666655 8.0000000056414375 0
		-0.16666666666666671 9.3333333274833183 -0
		-0.16666666666666671 9.9999999998679723 -0
		0.16666666666666657 1.3202807952317105e-10 0
		0.16666666666666666 0.66666667251667322 -0
		0.16666666666666655 1.9999999943585707 -0
		0.16666666666666674 4.0000000041110679 0
		0.16666666666666674 5.9999999958889223 0
		0.16666666666666655 8.0000000056414375 0
		0.16666666666666671 9.3333333274833183 -0
		0.16666666666666671 9.9999999998679723 -0
		0.49999999999999967 1.3202807952317105e-10 0
		0.49999999999999989 0.66666667251667322 -0
		0.49999999999999994 1.9999999943585707 -0
		0.5 4.0000000041110679 0
		0.5 5.9999999958889223 0
		0.49999999999999956 8.0000000056414375 0
		0.50000000000000011 9.3333333274833183 -0
		0.50000000000000011 9.9999999998679723 -0
		
		;
createNode transform -n "hair_000_CRV" -p "hair_Rig_GRP";
	rename -uid "2AE289B8-4C8B-A2E4-1422-0ABC7FCE290F";
	setAttr ".v" no;
	setAttr -l on ".tx";
	setAttr -l on ".ty";
	setAttr -l on ".tz";
	setAttr -l on ".rx";
	setAttr -l on ".ry";
	setAttr -l on ".rz";
	setAttr -l on ".sx";
	setAttr -l on ".sy";
	setAttr -l on ".sz";
createNode nurbsCurve -n "hair_000_CRVShape" -p "hair_000_CRV";
	rename -uid "FFBD121E-40AB-C0A1-F181-E68650E34245";
	setAttr -k off ".v";
	setAttr ".tw" yes;
createNode nurbsCurve -n "hair_000_CRVShapeOrig" -p "hair_000_CRV";
	rename -uid "E8E18EBF-452D-40DC-33B5-858146B9085C";
	setAttr -k off ".v";
	setAttr ".io" yes;
	setAttr ".cc" -type "nurbsCurve" 
		3 3 0 no 3
		8 0 0 0 1 2 3 3 3
		6
		0 0 0
		0 2 0
		0 4 0
		0 6 0
		0 8 0
		0 10 0
		;
createNode transform -n "tipRig" -p "hair_NoTransform000_GRP";
	rename -uid "DA71B6DD-4155-41B5-D0A5-E08A023EABD2";
createNode transform -n "hairTip_002_GRP" -p "tipRig";
	rename -uid "6A1E1A44-4D97-F677-300B-F6A1446A5041";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr ".ro" 4;
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
	setAttr -l on ".twist";
createNode transform -n "hairTip_002_CTL" -p "hairTip_002_GRP";
	rename -uid "18A6FE7B-418C-CEA3-0B03-F087F2BB6878";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr ".ro" 4;
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
	setAttr -l on ".twist";
createNode nurbsCurve -n "hairTip_002_CTLShape" -p "hairTip_002_CTL";
	rename -uid "762383FD-4B6E-1C19-BD92-399BFB326232";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 8 2 no 3
		13 -2 -1 0 1 2 3 4 5 6 7 8 9 10
		11
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		-4.4327767502175526 1.4070942476024109e-32 -2.2979592950099322e-16
		-3.134446499564898 -1.919294936395389e-16 3.134446499564898
		-4.4403427878412899e-16 -2.7142929292443668e-16 4.4327767502175535
		3.134446499564898 -1.9192949363953888e-16 3.1344464995648975
		4.4327767502175526 -3.7014716840440396e-32 6.044962003119836e-16
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		;
createNode parentConstraint -n "hairTip_002_GRP_parentConstraint1" -p "hairTip_002_GRP";
	rename -uid "4F8595E5-4691-00F1-19D1-DFB38FF4436D";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hairTip_001_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".tg[0].tot" -type "double3" 0 1 0 ;
	setAttr ".rst" -type "double3" 0 12 0 ;
	setAttr -k on ".w0";
createNode transform -n "hairTip_004_GRP" -p "tipRig";
	rename -uid "F0D5736F-4D1A-C7D7-F28D-D5895C88DF2A";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr ".ro" 4;
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
	setAttr -l on ".twist";
createNode transform -n "hairTip_004_CTL" -p "hairTip_004_GRP";
	rename -uid "B6F8D705-4B09-3BD5-7B61-9A9591843270";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr ".ro" 4;
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
	setAttr -l on ".twist";
createNode nurbsCurve -n "hairTip_004_CTLShape" -p "hairTip_004_CTL";
	rename -uid "6DDBA150-49C4-6A11-EF2A-A88C2721FCD7";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 8 2 no 3
		13 -2 -1 0 1 2 3 4 5 6 7 8 9 10
		11
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		-4.4327767502175526 1.4070942476024109e-32 -2.2979592950099322e-16
		-3.134446499564898 -1.919294936395389e-16 3.134446499564898
		-4.4403427878412899e-16 -2.7142929292443668e-16 4.4327767502175535
		3.134446499564898 -1.9192949363953888e-16 3.1344464995648975
		4.4327767502175526 -3.7014716840440396e-32 6.044962003119836e-16
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		;
createNode parentConstraint -n "hairTip_004_GRP_parentConstraint1" -p "hairTip_004_GRP";
	rename -uid "AC61CC3F-494B-6BA9-FB62-6C9DE0CD2E07";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hairTip_003_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".tg[0].tot" -type "double3" 0 1 0 ;
	setAttr ".rst" -type "double3" 0 14 0 ;
	setAttr -k on ".w0";
createNode transform -n "hairTip_001_GRP" -p "tipRig";
	rename -uid "6E66C149-40C3-E7CB-3DE7-AAA3C87713AF";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr ".ro" 4;
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
	setAttr -l on ".twist";
createNode transform -n "hairTip_001_CTL" -p "hairTip_001_GRP";
	rename -uid "0F0F2BFC-4404-6FCD-6D27-188584427116";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr ".ro" 4;
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
	setAttr -l on ".twist";
createNode nurbsCurve -n "hairTip_001_CTLShape" -p "hairTip_001_CTL";
	rename -uid "7449EE13-4467-9CCB-25D8-62899EB5CD93";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 8 2 no 3
		13 -2 -1 0 1 2 3 4 5 6 7 8 9 10
		11
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		-4.4327767502175526 1.4070942476024109e-32 -2.2979592950099322e-16
		-3.134446499564898 -1.919294936395389e-16 3.134446499564898
		-4.4403427878412899e-16 -2.7142929292443668e-16 4.4327767502175535
		3.134446499564898 -1.9192949363953888e-16 3.1344464995648975
		4.4327767502175526 -3.7014716840440396e-32 6.044962003119836e-16
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		;
createNode parentConstraint -n "hairTip_001_GRP_parentConstraint1" -p "hairTip_001_GRP";
	rename -uid "300EC269-4DE1-36A2-24E2-6E82B49BF909";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hairTop_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".tg[0].tot" -type "double3" -3.4694469519536142e-18 1 0 ;
	setAttr ".rst" -type "double3" -3.4694469519536142e-18 11 0 ;
	setAttr -k on ".w0";
createNode transform -n "hairTip_003_GRP" -p "tipRig";
	rename -uid "CA081B90-4F36-F1BA-38CC-56B50AF73028";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr ".ro" 4;
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
	setAttr -l on ".twist";
createNode transform -n "hairTip_003_CTL" -p "hairTip_003_GRP";
	rename -uid "537CB65C-4D23-F6A2-882A-8BA5FA41805A";
	addAttr -ci true -sn "twist" -ln "twist" -at "double";
	setAttr -l on -k off ".v";
	setAttr ".ro" 4;
	setAttr -l on -k off ".sx";
	setAttr -l on -k off ".sy";
	setAttr -l on -k off ".sz";
	setAttr -l on ".twist";
createNode nurbsCurve -n "hairTip_003_CTLShape" -p "hairTip_003_CTL";
	rename -uid "80DDA335-4CBC-5FB9-98CD-62B8543677CA";
	setAttr -k off ".v";
	setAttr ".ove" yes;
	setAttr ".ovc" 22;
	setAttr ".cc" -type "nurbsCurve" 
		3 8 2 no 3
		13 -2 -1 0 1 2 3 4 5 6 7 8 9 10
		11
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		-4.4327767502175526 1.4070942476024109e-32 -2.2979592950099322e-16
		-3.134446499564898 -1.919294936395389e-16 3.134446499564898
		-4.4403427878412899e-16 -2.7142929292443668e-16 4.4327767502175535
		3.134446499564898 -1.9192949363953888e-16 3.1344464995648975
		4.4327767502175526 -3.7014716840440396e-32 6.044962003119836e-16
		3.134446499564898 1.9192949363953893e-16 -3.1344464995648984
		2.7142929292443649e-16 2.7142929292443649e-16 -4.4327767502175508
		-3.134446499564898 1.9192949363953888e-16 -3.1344464995648975
		;
createNode parentConstraint -n "hairTip_003_GRP_parentConstraint1" -p "hairTip_003_GRP";
	rename -uid "F7E1FAAA-429A-78FD-8F59-E2A6A7A8CF3F";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hairTip_002_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".tg[0].tot" -type "double3" 0 1 0 ;
	setAttr ".rst" -type "double3" 0 13 0 ;
	setAttr -k on ".w0";
createNode joint -n "hairTip_000_SKL" -p "tipRig";
	rename -uid "0AD076B3-4988-298A-C23D-09B9BF3F2477";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".jo" -type "double3" 0 0 90 ;
	setAttr ".radi" 0.5;
createNode joint -n "hairTip_001_SKL" -p "hairTip_000_SKL";
	rename -uid "A4EB21F7-4408-1C90-EF02-F6A19E67F35D";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".radi" 0.5;
createNode joint -n "hairTip_002_SKL" -p "hairTip_001_SKL";
	rename -uid "C1C4B47E-42E7-E66F-F124-428B6F0502E0";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".radi" 0.5;
createNode joint -n "hairTip_003_SKL" -p "hairTip_002_SKL";
	rename -uid "221A447C-4B86-B5E8-3CEF-3A9E368AC9EB";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".radi" 0.5;
createNode joint -n "hairTip_004_SKL" -p "hairTip_003_SKL";
	rename -uid "D2B52D29-47C7-148F-22E5-77BCC706F23E";
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".radi" 0.5;
createNode joint -n "hairTip_005_SKL" -p "hairTip_004_SKL";
	rename -uid "F20D0771-491D-9AE3-D24C-AC9354568FF7";
	setAttr ".t" -type "double3" 1 0 0 ;
	setAttr ".mnrl" -type "double3" -360 -360 -360 ;
	setAttr ".mxrl" -type "double3" 360 360 360 ;
	setAttr ".jot" -type "string" "none";
	setAttr ".radi" 0.5;
createNode parentConstraint -n "hairTip_004_SKL_parentConstraint1" -p "hairTip_004_SKL";
	rename -uid "9185A0E6-44DA-86C0-FDC9-26821FB5D37E";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hairTip_004_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".tg[0].tor" -type "double3" 0 0 90 ;
	setAttr ".rst" -type "double3" 1 0 0 ;
	setAttr -k on ".w0";
createNode parentConstraint -n "hairTip_003_SKL_parentConstraint1" -p "hairTip_003_SKL";
	rename -uid "B49C28D2-49EE-E55B-B628-DB839FCB04F6";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hairTip_003_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".tg[0].tor" -type "double3" 0 0 90 ;
	setAttr ".rst" -type "double3" 1 0 0 ;
	setAttr -k on ".w0";
createNode parentConstraint -n "hairTip_002_SKL_parentConstraint1" -p "hairTip_002_SKL";
	rename -uid "0910D096-4F0A-EFBC-108E-8A9D7C4E3845";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hairTip_002_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".tg[0].tor" -type "double3" 0 0 90 ;
	setAttr ".rst" -type "double3" 1 0 0 ;
	setAttr -k on ".w0";
createNode parentConstraint -n "hairTip_001_SKL_parentConstraint1" -p "hairTip_001_SKL";
	rename -uid "4DC92DEB-414D-80B6-9A23-D1B97051D3AF";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hairTip_001_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".tg[0].tor" -type "double3" 0 0 90 ;
	setAttr ".rst" -type "double3" 1 0 0 ;
	setAttr -k on ".w0";
createNode parentConstraint -n "hairTip_000_SKL_parentConstraint1" -p "hairTip_000_SKL";
	rename -uid "EEBB2D2E-46B5-3938-D1C9-A387F17E0557";
	addAttr -dcb 0 -ci true -k true -sn "w0" -ln "hairTop_CTLW0" -dv 1 -min 0 -at "double";
	setAttr -k on ".nds";
	setAttr -k off ".v";
	setAttr -k off ".tx";
	setAttr -k off ".ty";
	setAttr -k off ".tz";
	setAttr -k off ".rx";
	setAttr -k off ".ry";
	setAttr -k off ".rz";
	setAttr -k off ".sx";
	setAttr -k off ".sy";
	setAttr -k off ".sz";
	setAttr ".erp" yes;
	setAttr ".tg[0].tor" -type "double3" 0 0 90 ;
	setAttr ".rst" -type "double3" 0 10 0 ;
	setAttr -k on ".w0";
createNode transform -n "pSphere1";
	rename -uid "4AA6C58B-4E59-4D07-AE25-91BD83200A26";
createNode mesh -n "pSphereShape1" -p "pSphere1";
	rename -uid "349B1473-4539-9F30-11BA-32B3FB9A8D73";
	setAttr -k off ".v";
	setAttr ".vir" yes;
	setAttr ".vif" yes;
	setAttr ".uvst[0].uvsn" -type "string" "map1";
	setAttr ".cuvs" -type "string" "map1";
	setAttr ".dcc" -type "string" "Ambient+Diffuse";
	setAttr ".covm[0]"  0 1 1;
	setAttr ".cdvm[0]"  0 1 1;
createNode lightLinker -s -n "lightLinker1";
	rename -uid "8249DEEB-410E-6E7D-BB5D-0D83F6E2CBA8";
	setAttr -s 2 ".lnk";
	setAttr -s 2 ".slnk";
createNode shapeEditorManager -n "shapeEditorManager";
	rename -uid "13300EAE-452F-0229-588C-449B00CE9FEC";
createNode poseInterpolatorManager -n "poseInterpolatorManager";
	rename -uid "884368FE-42C2-13B0-A586-859DD831660B";
createNode displayLayerManager -n "layerManager";
	rename -uid "413A1752-4236-1A95-8553-ED812CE192CA";
createNode displayLayer -n "defaultLayer";
	rename -uid "D142B23E-401D-C018-80E1-6C93C1F2EB7F";
	setAttr ".ufem" -type "stringArray" 0  ;
createNode renderLayerManager -n "renderLayerManager";
	rename -uid "03C1C997-4B0A-43D6-91ED-15A820E68464";
createNode renderLayer -n "defaultRenderLayer";
	rename -uid "D0FAA640-4BFB-9649-8B22-0E9CAC3AC2C1";
	setAttr ".g" yes;
createNode aiOptions -s -n "defaultArnoldRenderOptions";
	rename -uid "96373DCA-4C71-460D-B632-20ADC7DEA2A7";
	setAttr ".version" -type "string" "5.4.8.2";
createNode aiAOVFilter -s -n "defaultArnoldFilter";
	rename -uid "F56FD19B-465C-CE6F-6692-04B8D965A942";
	setAttr ".ai_translator" -type "string" "gaussian";
createNode aiAOVDriver -s -n "defaultArnoldDriver";
	rename -uid "3CC1923F-45C9-B0FD-0BB9-EC905C67400D";
	setAttr ".ai_translator" -type "string" "exr";
createNode aiAOVDriver -s -n "defaultArnoldDisplayDriver";
	rename -uid "6FBE0C15-4F2A-F216-E5F4-FABA45EA91B2";
	setAttr ".ai_translator" -type "string" "maya";
	setAttr ".output_mode" 0;
createNode aiImagerDenoiserOidn -s -n "defaultArnoldDenoiser";
	rename -uid "60825DDF-46EE-7D92-B738-DFB06064BC24";
createNode ikSplineSolver -n "ikSplineSolver";
	rename -uid "5D533F02-41F7-8DFC-1B41-05AB57E08D1D";
createNode multiplyDivide -n "hair_Twist000_MDN";
	rename -uid "C74393B5-469A-858B-3078-F58AB7F130D2";
	setAttr ".i2" -type "float3" 0 0 1 ;
createNode unitConversion -n "unitConversion1";
	rename -uid "A30EF563-415A-6379-904D-33BCA9C7E43F";
	setAttr ".cf" 57.295779513082323;
createNode multiplyDivide -n "hair_Twist001_MDN";
	rename -uid "074690D3-4DE4-5487-9CF8-EAA6222D943C";
	setAttr ".i2" -type "float3" 0.2 0.40000001 0.80000001 ;
createNode unitConversion -n "unitConversion2";
	rename -uid "D0031393-4351-5086-41B2-1B81CD105493";
	setAttr ".cf" 57.295779513082323;
createNode multiplyDivide -n "hair_Twist002_MDN";
	rename -uid "E0D4D611-40CB-EF76-8E53-20B6A69F539F";
	setAttr ".i2" -type "float3" 0.40000001 0.80000001 0.60000002 ;
createNode unitConversion -n "unitConversion3";
	rename -uid "4827C4A3-4A4E-E7E8-DA4F-B49A1D3029AE";
	setAttr ".cf" 57.295779513082323;
createNode multiplyDivide -n "hair_Twist003_MDN";
	rename -uid "1DA2BAA0-4407-8CA5-E4C3-86B2B0FACFD4";
	setAttr ".i2" -type "float3" 0.60000002 1.2 0.40000001 ;
createNode unitConversion -n "unitConversion4";
	rename -uid "45CCFE36-4C45-F367-E130-D5A86B3B68A4";
	setAttr ".cf" 57.295779513082323;
createNode multiplyDivide -n "hair_Twist004_MDN";
	rename -uid "4DE8F023-4CC2-5613-7D3F-9EA6D05F858F";
	setAttr ".i2" -type "float3" 0.80000001 0.40000001 0.2 ;
createNode unitConversion -n "unitConversion5";
	rename -uid "3EDB0585-4136-227B-0143-3CA1E3C22296";
	setAttr ".cf" 57.295779513082323;
createNode multiplyDivide -n "hair_Twist005_MDN";
	rename -uid "AEE92665-4C5C-F2A1-F082-0FB23609334A";
	setAttr ".i2" -type "float3" 1 0 0 ;
createNode unitConversion -n "unitConversion6";
	rename -uid "ACC47F7B-4450-C116-8591-A8A0C3FA7A82";
	setAttr ".cf" 57.295779513082323;
createNode plusMinusAverage -n "hair_Twist000_PMA";
	rename -uid "D1F7D9CC-4EE4-DC13-C3EC-F2BCBC65C186";
	setAttr -s 3 ".i1";
	setAttr -s 3 ".i1";
createNode plusMinusAverage -n "hair_Twist001_PMA";
	rename -uid "3CDD66C4-42D1-4F18-4AA1-888636193BF8";
	setAttr -s 3 ".i1";
	setAttr -s 3 ".i1";
createNode plusMinusAverage -n "hair_Twist002_PMA";
	rename -uid "1E23CC4F-45EA-A4FF-A77C-839E2D1AE577";
	setAttr -s 3 ".i1";
	setAttr -s 3 ".i1";
createNode plusMinusAverage -n "hair_Twist003_PMA";
	rename -uid "C4E703E6-4E99-25D3-554A-49BD2EA1E45C";
	setAttr -s 3 ".i1";
	setAttr -s 3 ".i1";
createNode plusMinusAverage -n "hair_Twist004_PMA";
	rename -uid "68E982FC-4416-5831-17FE-D9907413491D";
	setAttr -s 3 ".i1";
	setAttr -s 3 ".i1";
createNode plusMinusAverage -n "hair_Twist005_PMA";
	rename -uid "059F8480-4DA0-96F7-3113-88B97D1D46D6";
	setAttr -s 3 ".i1";
	setAttr -s 3 ".i1";
createNode unitConversion -n "unitConversion7";
	rename -uid "A9B7DABD-46AB-69BC-0765-D89FEC1A4DC2";
	setAttr ".cf" 0.017453292519943295;
createNode unitConversion -n "unitConversion8";
	rename -uid "538FA5E5-40D5-A55A-DF55-FFBC1A8CC0D6";
	setAttr ".cf" 0.017453292519943295;
createNode unitConversion -n "unitConversion9";
	rename -uid "FC246D4B-4AD3-20A3-A601-34B0AB2F8DB9";
	setAttr ".cf" 0.017453292519943295;
createNode unitConversion -n "unitConversion10";
	rename -uid "721F51A7-4D72-38BB-5FDB-EFA8B1BBD9A4";
	setAttr ".cf" 0.017453292519943295;
createNode unitConversion -n "unitConversion11";
	rename -uid "9E999AA5-4C9F-202A-523F-589EBF593DF9";
	setAttr ".cf" 0.017453292519943295;
createNode unitConversion -n "unitConversion12";
	rename -uid "A48AFE6F-4C4C-8F6F-BD84-AF9517C1F949";
	setAttr ".cf" 0.017453292519943295;
createNode curveInfo -n "hair_000_CIN";
	rename -uid "3991C1B5-4B04-A674-161D-68ADB8EA994A";
createNode multiplyDivide -n "hair_SquashStretch000_MDN";
	rename -uid "AEFBE9A1-410A-DE17-BBE0-369EB7109EFB";
	setAttr ".op" 2;
createNode skinCluster -n "hair_Geo000_SKN";
	rename -uid "94A08343-4319-0521-82A1-C291C2DBE3EF";
	setAttr -s 32 ".wl";
	setAttr ".wl[0:31].w"
		2 0 0.99999861028879844 1 1.3897112015290878e-06
		2 0 0.99998113267303745 1 1.8867326962567397e-05
		2 0 0.99778589659372674 1 0.0022141034062732861
		2 0 0.85879039750526287 1 0.14120960249473713
		2 0 0.14120960249473941 1 0.85879039750526065
		2 0 0.0022141034062732367 1 0.99778589659372674
		2 0 1.8867326962568179e-05 1 0.99998113267303745
		2 0 1.3897112015290933e-06 1 0.99999861028879844
		2 0 0.99999999004484619 1 9.9551537693481986e-09
		2 0 0.99999203200665066 1 7.9679933494217819e-06
		2 0 0.99802208075451315 1 0.001977919245486885
		2 0 0.86085692022074189 1 0.13914307977925813
		2 0 0.13914307977926033 1 0.86085692022073979
		2 0 0.0019779192454868395 1 0.99802208075451315
		2 0 7.9679933494222443e-06 1 0.99999203200665066
		2 0 9.9551537693482366e-09 1 0.99999999004484619
		2 0 0.99999999004484619 1 9.9551537693481986e-09
		2 0 0.99999203200665066 1 7.9679933494217819e-06
		2 0 0.99802208075451315 1 0.001977919245486885
		2 0 0.86085692022074189 1 0.13914307977925813
		2 0 0.13914307977926033 1 0.86085692022073979
		2 0 0.0019779192454868395 1 0.99802208075451315
		2 0 7.9679933494222443e-06 1 0.99999203200665066
		2 0 9.9551537693482366e-09 1 0.99999999004484619
		2 0 0.99999861028879844 1 1.3897112015290878e-06
		2 0 0.99998113267303745 1 1.8867326962567397e-05
		2 0 0.99778589659372674 1 0.0022141034062732861
		2 0 0.85879039750526287 1 0.14120960249473713
		2 0 0.14120960249473941 1 0.85879039750526065
		2 0 0.0022141034062732367 1 0.99778589659372674
		2 0 1.8867326962568179e-05 1 0.99998113267303745
		2 0 1.3897112015290933e-06 1 0.99999861028879844;
	setAttr -s 2 ".pm";
	setAttr ".pm[0]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 0 -0 1;
	setAttr ".pm[1]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 -10 -0 1;
	setAttr ".gm" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr -s 2 ".ma";
	setAttr -s 2 ".dpf[0:1]"  4.5 4.5;
	setAttr -s 2 ".lw";
	setAttr -s 2 ".lw";
	setAttr ".bm" 1;
	setAttr ".ucm" yes;
	setAttr -s 2 ".ifcl";
	setAttr -s 2 ".ifcl";
createNode tweak -n "tweak1";
	rename -uid "D62DA951-49D8-5C38-EDD8-51B21D0D113E";
createNode dagPose -n "bindPose1";
	rename -uid "44A72992-49F9-8855-7B64-0CB1A30ABCA2";
	setAttr -s 7 ".wm";
	setAttr ".wm[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".wm[2]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr ".wm[4]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 4.9999999999999947 0 1;
	setAttr ".wm[5]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 4.9999999999999947 0 1;
	setAttr -s 7 ".xm";
	setAttr ".xm[0]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[1]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[2]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[3]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 10 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[4]" -type "matrix" "xform" 1 1 1 0 -0 0 0 0 4.9999999999999947
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[5]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[6]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr -s 7 ".m";
	setAttr -s 7 ".p";
	setAttr -s 7 ".g[0:6]" yes no yes no yes yes no;
	setAttr ".bp" yes;
createNode skinCluster -n "hair_Geo001_SKN";
	rename -uid "8082376A-4814-B129-7F65-E3A9BE9132D5";
	setAttr -s 32 ".wl";
	setAttr ".wl[0:31].w"
		2 0 0.99996907829164494 2 3.0921708355035867e-05
		2 0 0.99941815342672036 2 0.00058184657327967277
		2 0 0.85193202721803796 2 0.14806797278196213
		2 0 0.0031065346218287983 2 0.99689346537817125
		2 1 0.0031065346218287757 2 0.99689346537817125
		2 1 0.85193202721804351 2 0.14806797278195652
		2 1 0.99941815342672036 2 0.00058184657327969337
		2 1 0.99996907829164494 2 3.0921708355035697e-05
		2 0 0.99999977516230587 2 2.2483769415952719e-07
		2 0 0.9997490561306821 2 0.00025094386931794998
		2 0 0.86008014240961006 2 0.13991985759039002
		2 0 0.0020649548677129266 2 0.99793504513228715
		2 1 0.0020649548677129119 2 0.99793504513228715
		2 1 0.8600801424096155 2 0.1399198575903845
		2 1 0.99974905613068199 2 0.00025094386931796305
		2 1 0.99999977516230587 2 2.2483769415952586e-07
		2 0 0.99999977516230587 2 2.2483769415952719e-07
		2 0 0.9997490561306821 2 0.00025094386931794998
		2 0 0.86008014240961006 2 0.13991985759039002
		2 0 0.0020649548677129266 2 0.99793504513228715
		2 1 0.0020649548677129119 2 0.99793504513228715
		2 1 0.8600801424096155 2 0.1399198575903845
		2 1 0.99974905613068199 2 0.00025094386931796305
		2 1 0.99999977516230587 2 2.2483769415952586e-07
		2 0 0.99996907829164494 2 3.0921708355035867e-05
		2 0 0.99941815342672036 2 0.00058184657327967277
		2 0 0.85193202721803796 2 0.14806797278196213
		2 0 0.0031065346218287983 2 0.99689346537817125
		2 1 0.0031065346218287757 2 0.99689346537817125
		2 1 0.85193202721804351 2 0.14806797278195652
		2 1 0.99941815342672036 2 0.00058184657327969337
		2 1 0.99996907829164494 2 3.0921708355035697e-05;
	setAttr -s 3 ".pm";
	setAttr ".pm[0]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 0 -0 1;
	setAttr ".pm[1]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 -10 -0 1;
	setAttr ".pm[2]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 -4.9999999999999947 -0 1;
	setAttr ".gm" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr -s 3 ".ma";
	setAttr -s 3 ".dpf[0:2]"  4.5 4.5 4.5;
	setAttr -s 3 ".lw";
	setAttr -s 3 ".lw";
	setAttr ".bm" 1;
	setAttr ".ucm" yes;
	setAttr -s 3 ".ifcl";
	setAttr -s 3 ".ifcl";
createNode tweak -n "tweak2";
	rename -uid "85D38A6B-4F10-5ED1-CF29-BFA5FF4F23A3";
createNode skinCluster -n "hair_Crv000_SKN";
	rename -uid "31BC559F-46E8-805F-FF8A-C18BA6741F0D";
	setAttr -s 6 ".wl";
	setAttr ".wl[0:5].w"
		1 0 1
		1 1 1
		1 2 1
		1 3 1
		1 4 1
		1 5 1;
	setAttr -s 6 ".pm";
	setAttr ".pm[0]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 -1.3202807952317105e-10 -0 1;
	setAttr ".pm[1]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 -1.999999998856846 -0 1;
	setAttr ".pm[2]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 -4.0000000011152945 -0 1;
	setAttr ".pm[3]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 -5.9999999988846984 -0 1;
	setAttr ".pm[4]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 -8.0000000011431567 -0 1;
	setAttr ".pm[5]" -type "matrix" 1 -0 0 -0 -0 1 -0 0 0 -0 1 -0 -0 -9.9999999998679741 -0 1;
	setAttr ".gm" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1;
	setAttr -s 6 ".ma";
	setAttr -s 6 ".dpf[0:5]"  4 4 4 4 4 4;
	setAttr -s 6 ".lw";
	setAttr -s 6 ".lw";
	setAttr ".bm" 1;
	setAttr ".ucm" yes;
	setAttr -s 6 ".ifcl";
	setAttr -s 6 ".ifcl";
createNode tweak -n "tweak3";
	rename -uid "7E55177C-4A8E-796D-A42B-C7AE2F0EC2FD";
createNode dagPose -n "bindPose2";
	rename -uid "D726F49F-491F-016C-D01D-07921CF9154A";
	setAttr -s 12 ".wm";
	setAttr ".wm[0]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 1.3202807952317105e-10 0 1;
	setAttr ".wm[2]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 1.999999998856846 0 1;
	setAttr ".wm[4]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 4.0000000011152945 0 1;
	setAttr ".wm[6]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 5.9999999988846984 0 1;
	setAttr ".wm[8]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 8.0000000011431567 0 1;
	setAttr ".wm[10]" -type "matrix" 1 0 0 0 0 1 0 0 0 0 1 0 0 9.9999999998679741 0 1;
	setAttr -s 12 ".xm";
	setAttr ".xm[0]" -type "matrix" "xform" 1 1 1 0 -0 0 0 0 1.3202807952317105e-10
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[1]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[2]" -type "matrix" "xform" 1 1 1 0 -0 0 0 0 1.999999998856846 0 0
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[3]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[4]" -type "matrix" "xform" 1 1 1 0 -0 0 0 0 4.0000000011152945
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[5]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[6]" -type "matrix" "xform" 1 1 1 0 -0 0 0 0 5.9999999988846984
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[7]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[8]" -type "matrix" "xform" 1 1 1 0 -0 0 0 0 8.0000000011431567
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[9]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[10]" -type "matrix" "xform" 1 1 1 0 -0 0 0 0 9.9999999998679741
		 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr ".xm[11]" -type "matrix" "xform" 1 1 1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
		 0 0 0 0 0 0 0 0 0 0 1 0 0 0 1 1 1 1 yes;
	setAttr -s 12 ".m";
	setAttr -s 12 ".p";
	setAttr -s 12 ".g[0:11]" yes no yes no yes no yes no yes no yes no;
	setAttr ".bp" yes;
createNode animCurveUA -n "hair_CTL001_TopSDK_GRP_rotateZ";
	rename -uid "439108B8-45BA-C5F4-36E9-309C035336A9";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr -s 3 ".ktv[0:2]"  -10 90 0 0 10 -90;
createNode animCurveUA -n "hair_CTL001_TopRotateSDK_GRP_rotateZ";
	rename -uid "C5112938-45E4-0557-ADA2-E48D4037F897";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr -s 3 ".ktv[0:2]"  -90 90 0 0 90 -90;
createNode unitConversion -n "unitConversion13";
	rename -uid "FEFB1882-40EC-21C0-1DFA-E0B4A9AE5AFA";
	setAttr ".cf" 57.295779513082323;
createNode animCurveUA -n "hair_CTL001_BtmRotateSDK_GRP_rotateZ";
	rename -uid "591BB283-4059-4717-41E8-3CB8F80BFE0E";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr -s 3 ".ktv[0:2]"  -90 90 0 0 90 -90;
createNode unitConversion -n "unitConversion14";
	rename -uid "80655EC7-464F-8AD2-7520-05AA01268E9B";
	setAttr ".cf" 57.295779513082323;
createNode animCurveUA -n "hair_CTL001_BtmSDK_GRP_rotateZ";
	rename -uid "04428CA0-499A-6BD4-90C8-81895D24ABBD";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr -s 3 ".ktv[0:2]"  -10 -90 0 0 10 90;
createNode multiplyDivide -n "hair_GlobalScale000_MDN";
	rename -uid "CEF31947-4E3E-F740-7F77-E2B5F96C52EA";
	setAttr ".i1" -type "float3" 10 0 0 ;
createNode addDoubleLinear -n "hairExtraTwist000_ADL";
	rename -uid "25BCEAD9-49C8-C267-F847-36A43C93BDD7";
	setAttr ".ihi" 2;
createNode addDoubleLinear -n "hairExtraTwist002_ADL";
	rename -uid "95BAA844-4059-40E1-5505-BA86A839BD75";
	setAttr ".ihi" 2;
createNode unitConversion -n "unitConversion15";
	rename -uid "354F6B02-4007-8845-ED6D-C3B8E2315F9E";
	setAttr ".cf" 57.295779513082323;
createNode unitConversion -n "unitConversion16";
	rename -uid "49C03FC0-45C7-5B0A-B308-CAA898B4DEEB";
	setAttr ".cf" 57.295779513082323;
createNode script -n "uiConfigurationScriptNode";
	rename -uid "BEDD6D7C-4740-07E5-66B5-D0AE674CBCCE";
	setAttr ".b" -type "string" (
		"// Maya Mel UI Configuration File.\n//\n//  This script is machine generated.  Edit at your own risk.\n//\n//\n\nglobal string $gMainPane;\nif (`paneLayout -exists $gMainPane`) {\n\n\tglobal int $gUseScenePanelConfig;\n\tint    $useSceneConfig = $gUseScenePanelConfig;\n\tint    $nodeEditorPanelVisible = stringArrayContains(\"nodeEditorPanel1\", `getPanel -vis`);\n\tint    $nodeEditorWorkspaceControlOpen = (`workspaceControl -exists nodeEditorPanel1Window` && `workspaceControl -q -visible nodeEditorPanel1Window`);\n\tint    $menusOkayInPanels = `optionVar -q allowMenusInPanels`;\n\tint    $nVisPanes = `paneLayout -q -nvp $gMainPane`;\n\tint    $nPanes = 0;\n\tstring $editorName;\n\tstring $panelName;\n\tstring $itemFilterName;\n\tstring $panelConfig;\n\n\t//\n\t//  get current state of the UI\n\t//\n\tsceneUIReplacement -update $gMainPane;\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Top View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Top View\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"|top\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 16384\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n"
		+ "            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n"
		+ "            -hulls 1\n            -grid 0\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -bluePencil 1\n            -greasePencils 0\n            -excludeObjectPreset \"All\" \n            -shadows 0\n            -captureSequenceNumber -1\n            -width 752\n            -height 293\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Side View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Side View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"|side\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n"
		+ "            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 16384\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n"
		+ "            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 0\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -bluePencil 1\n            -greasePencils 0\n            -excludeObjectPreset \"All\" \n"
		+ "            -shadows 0\n            -captureSequenceNumber -1\n            -width 751\n            -height 293\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Front View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Front View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"|front\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n"
		+ "            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 16384\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n"
		+ "            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 0\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n"
		+ "            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -bluePencil 1\n            -greasePencils 0\n            -excludeObjectPreset \"All\" \n            -shadows 0\n            -captureSequenceNumber -1\n            -width 752\n            -height 293\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Persp View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Persp View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n"
		+ "        modelEditor -e \n            -camera \"|front\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 16384\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n"
		+ "            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n"
		+ "            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -bluePencil 1\n            -greasePencils 0\n            -excludeObjectPreset \"All\" \n            -shadows 0\n            -captureSequenceNumber -1\n            -width 1499\n            -height 653\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n"
		+ "\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"ToggledOutliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"ToggledOutliner\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -showShapes 0\n            -showAssignedMaterials 0\n            -showTimeEditor 1\n            -showReferenceNodes 1\n            -showReferenceMembers 1\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n            -showContainerContents 1\n            -ignoreDagHierarchy 0\n"
		+ "            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n            -doNotSelectNewObjects 0\n            -dropIsParent 1\n            -transmitFilters 0\n            -setFilter \"defaultSetFilter\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -isSet 0\n            -isSetMember 0\n            -showUfeItems 1\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n"
		+ "            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            -renderFilterIndex 0\n            -selectionOrder \"chronological\" \n            -expandAttribute 0\n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"Outliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"Outliner\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -showShapes 0\n            -showAssignedMaterials 0\n            -showTimeEditor 1\n            -showReferenceNodes 0\n            -showReferenceMembers 0\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n"
		+ "            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n            -showContainerContents 1\n            -ignoreDagHierarchy 0\n            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n            -doNotSelectNewObjects 0\n            -dropIsParent 1\n            -transmitFilters 0\n            -setFilter \"defaultSetFilter\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -showUfeItems 1\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n"
		+ "            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"graphEditor\" (localizedPanelLabel(\"Graph Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Graph Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n            outlinerEditor -e \n                -showShapes 1\n"
		+ "                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n                -autoExpand 1\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 0\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n                -showUpstreamCurves 1\n                -showUnitlessCurves 1\n                -showCompounds 0\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n                -autoSelectNewObjects 1\n                -doNotSelectNewObjects 0\n"
		+ "                -dropIsParent 1\n                -transmitFilters 1\n                -setFilter \"0\" \n                -showSetMembers 0\n                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -showUfeItems 1\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n                -containersIgnoreFilters 0\n                -editAttrName 0\n                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 1\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n                $editorName;\n"
		+ "\n\t\t\t$editorName = ($panelName+\"GraphEd\");\n            animCurveEditor -e \n                -displayValues 0\n                -snapTime \"integer\" \n                -snapValue \"none\" \n                -showPlayRangeShades \"on\" \n                -lockPlayRangeShades \"off\" \n                -smoothness \"fine\" \n                -resultSamples 1\n                -resultScreenSamples 0\n                -resultUpdate \"delayed\" \n                -showUpstreamCurves 1\n                -tangentScale 1\n                -tangentLineThickness 1\n                -keyMinScale 1\n                -stackedCurvesMin -1\n                -stackedCurvesMax 1\n                -stackedCurvesSpace 0.2\n                -preSelectionHighlight 0\n                -limitToSelectedCurves 0\n                -constrainDrag 0\n                -valueLinesToggle 0\n                -highlightAffectedCurves 0\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dopeSheetPanel\" (localizedPanelLabel(\"Dope Sheet\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dope Sheet\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n            outlinerEditor -e \n                -showShapes 1\n                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n                -autoExpand 1\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 0\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n"
		+ "                -showUpstreamCurves 1\n                -showUnitlessCurves 0\n                -showCompounds 0\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n                -autoSelectNewObjects 0\n                -doNotSelectNewObjects 1\n                -dropIsParent 1\n                -transmitFilters 0\n                -setFilter \"0\" \n                -showSetMembers 1\n                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -showUfeItems 1\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n                -containersIgnoreFilters 0\n                -editAttrName 0\n                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n"
		+ "                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 0\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n                $editorName;\n\n\t\t\t$editorName = ($panelName+\"DopeSheetEd\");\n            dopeSheetEditor -e \n                -displayValues 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -outliner \"dopeSheetPanel1OutlineEd\" \n                -hierarchyBelow 0\n                -selectionWindow 0 0 0 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"timeEditorPanel\" (localizedPanelLabel(\"Time Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Time Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n"
		+ "\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"clipEditorPanel\" (localizedPanelLabel(\"Trax Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Trax Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = clipEditorNameFromPanel($panelName);\n            clipEditor -e \n                -displayValues 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"sequenceEditorPanel\" (localizedPanelLabel(\"Camera Sequencer\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Camera Sequencer\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = sequenceEditorNameFromPanel($panelName);\n            clipEditor -e \n                -displayValues 0\n"
		+ "                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 1 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperGraphPanel\" (localizedPanelLabel(\"Hypergraph Hierarchy\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypergraph Hierarchy\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"HyperGraphEd\");\n            hyperGraph -e \n                -graphLayoutStyle \"hierarchicalLayout\" \n                -orientation \"horiz\" \n                -mergeConnections 0\n                -zoom 1\n                -animateTransition 0\n                -showRelationships 1\n                -showShapes 0\n                -showDeformers 0\n                -showExpressions 0\n                -showConstraints 0\n                -showConnectionFromSelected 0\n                -showConnectionToSelected 0\n"
		+ "                -showConstraintLabels 0\n                -showUnderworld 0\n                -showInvisible 0\n                -transitionFrames 1\n                -opaqueContainers 0\n                -freeform 0\n                -imagePosition 0 0 \n                -imageScale 1\n                -imageEnabled 0\n                -graphType \"DAG\" \n                -heatMapDisplay 0\n                -updateSelection 1\n                -updateNodeAdded 1\n                -useDrawOverrideColor 0\n                -limitGraphTraversal -1\n                -range 0 0 \n                -iconSize \"smallIcons\" \n                -showCachedConnections 0\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperShadePanel\" (localizedPanelLabel(\"Hypershade\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypershade\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n"
		+ "\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"visorPanel\" (localizedPanelLabel(\"Visor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Visor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"nodeEditorPanel\" (localizedPanelLabel(\"Node Editor\")) `;\n\tif ($nodeEditorPanelVisible || $nodeEditorWorkspaceControlOpen) {\n\t\tif (\"\" == $panelName) {\n\t\t\tif ($useSceneConfig) {\n\t\t\t\t$panelName = `scriptedPanel -unParent  -type \"nodeEditorPanel\" -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels `;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n                -connectNodeOnCreation 0\n"
		+ "                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -connectionStyle \"bezier\" \n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -connectedGraphingMode 1\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n                -keyPressCommand \"nodeEdKeyPressCommand\" \n                -nodeTitleMode \"name\" \n                -gridSnap 0\n                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n                -showNamespace 1\n                -showShapes 1\n                -showSGShapes 0\n                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -showUnitConversions 0\n                -editorMode \"default\" \n                -hasWatchpoint 0\n                $editorName;\n\t\t\t}\n\t\t} else {\n\t\t\t$label = `panel -q -label $panelName`;\n"
		+ "\t\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n                -connectNodeOnCreation 0\n                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -connectionStyle \"bezier\" \n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -connectedGraphingMode 1\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n                -keyPressCommand \"nodeEdKeyPressCommand\" \n                -nodeTitleMode \"name\" \n                -gridSnap 0\n                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n                -showNamespace 1\n"
		+ "                -showShapes 1\n                -showSGShapes 0\n                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -showUnitConversions 0\n                -editorMode \"default\" \n                -hasWatchpoint 0\n                $editorName;\n\t\t\tif (!$useSceneConfig) {\n\t\t\t\tpanel -e -l $label $panelName;\n\t\t\t}\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"createNodePanel\" (localizedPanelLabel(\"Create Node\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Create Node\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"polyTexturePlacementPanel\" (localizedPanelLabel(\"UV Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"UV Editor\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"renderWindowPanel\" (localizedPanelLabel(\"Render View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Render View\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"shapePanel\" (localizedPanelLabel(\"Shape Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tshapePanel -edit -l (localizedPanelLabel(\"Shape Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"posePanel\" (localizedPanelLabel(\"Pose Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tposePanel -edit -l (localizedPanelLabel(\"Pose Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n"
		+ "\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynRelEdPanel\" (localizedPanelLabel(\"Dynamic Relationships\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dynamic Relationships\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"relationshipPanel\" (localizedPanelLabel(\"Relationship Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Relationship Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"referenceEditorPanel\" (localizedPanelLabel(\"Reference Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Reference Editor\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynPaintScriptedPanelType\" (localizedPanelLabel(\"Paint Effects\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Paint Effects\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"scriptEditorPanel\" (localizedPanelLabel(\"Script Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Script Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"profilerPanel\" (localizedPanelLabel(\"Profiler Tool\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Profiler Tool\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"contentBrowserPanel\" (localizedPanelLabel(\"Content Browser\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Content Browser\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"Stereo\" (localizedPanelLabel(\"Stereo\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Stereo\")) -mbv $menusOkayInPanels  $panelName;\n{ string $editorName = ($panelName+\"Editor\");\n            stereoCameraView -e \n                -camera \"|persp\" \n                -useInteractiveMode 0\n                -displayLights \"default\" \n                -displayAppearance \"smoothShaded\" \n                -activeOnly 0\n                -ignorePanZoom 0\n                -wireframeOnShaded 0\n"
		+ "                -headsUpDisplay 1\n                -holdOuts 1\n                -selectionHiliteDisplay 1\n                -useDefaultMaterial 0\n                -bufferMode \"double\" \n                -twoSidedLighting 0\n                -backfaceCulling 0\n                -xray 0\n                -jointXray 0\n                -activeComponentsXray 0\n                -displayTextures 0\n                -smoothWireframe 0\n                -lineWidth 1\n                -textureAnisotropic 0\n                -textureHilight 1\n                -textureSampling 2\n                -textureDisplay \"modulate\" \n                -textureMaxSize 16384\n                -fogging 0\n                -fogSource \"fragment\" \n                -fogMode \"linear\" \n                -fogStart 0\n                -fogEnd 100\n                -fogDensity 0.1\n                -fogColor 0.5 0.5 0.5 1 \n                -depthOfFieldPreview 1\n                -maxConstantTransparency 1\n                -objectFilterShowInHUD 1\n                -isFiltered 0\n                -colorResolution 4 4 \n"
		+ "                -bumpResolution 4 4 \n                -textureCompression 0\n                -transparencyAlgorithm \"frontAndBackCull\" \n                -transpInShadows 0\n                -cullingOverride \"none\" \n                -lowQualityLighting 0\n                -maximumNumHardwareLights 0\n                -occlusionCulling 0\n                -shadingModel 0\n                -useBaseRenderer 0\n                -useReducedRenderer 0\n                -smallObjectCulling 0\n                -smallObjectThreshold -1 \n                -interactiveDisableShadows 0\n                -interactiveBackFaceCull 0\n                -sortTransparent 1\n                -controllers 1\n                -nurbsCurves 1\n                -nurbsSurfaces 1\n                -polymeshes 1\n                -subdivSurfaces 1\n                -planes 1\n                -lights 1\n                -cameras 1\n                -controlVertices 1\n                -hulls 1\n                -grid 1\n                -imagePlane 1\n                -joints 1\n                -ikHandles 1\n"
		+ "                -deformers 1\n                -dynamics 1\n                -particleInstancers 1\n                -fluids 1\n                -hairSystems 1\n                -follicles 1\n                -nCloths 1\n                -nParticles 1\n                -nRigids 1\n                -dynamicConstraints 1\n                -locators 1\n                -manipulators 1\n                -pluginShapes 1\n                -dimensions 1\n                -handles 1\n                -pivots 1\n                -textures 1\n                -strokes 1\n                -motionTrails 1\n                -clipGhosts 1\n                -bluePencil 1\n                -greasePencils 0\n                -excludeObjectPreset \"All\" \n                -shadows 0\n                -captureSequenceNumber -1\n                -width 0\n                -height 0\n                -sceneRenderFilter 0\n                -displayMode \"centerEye\" \n                -viewColor 0 0 0 1 \n                -useCustomBackground 1\n                $editorName;\n            stereoCameraView -e -viewSelected 0 $editorName;\n"
		+ "            stereoCameraView -e \n                -pluginObjects \"gpuCacheDisplayFilter\" 1 \n                $editorName; };\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\tif ($useSceneConfig) {\n        string $configName = `getPanel -cwl (localizedPanelLabel(\"Current Layout\"))`;\n        if (\"\" != $configName) {\n\t\t\tpanelConfiguration -edit -label (localizedPanelLabel(\"Current Layout\")) \n\t\t\t\t-userCreated false\n\t\t\t\t-defaultImage \"vacantCell.xP:/\"\n\t\t\t\t-image \"\"\n\t\t\t\t-sc false\n\t\t\t\t-configString \"global string $gMainPane; paneLayout -e -cn \\\"single\\\" -ps 1 100 100 $gMainPane;\"\n\t\t\t\t-removeAllPanels\n\t\t\t\t-ap false\n\t\t\t\t\t(localizedPanelLabel(\"Persp View\")) \n\t\t\t\t\t\"modelPanel\"\n"
		+ "\t\t\t\t\t\"$panelName = `modelPanel -unParent -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels `;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -camera \\\"|front\\\" \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 16384\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -bluePencil 1\\n    -greasePencils 0\\n    -excludeObjectPreset \\\"All\\\" \\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 1499\\n    -height 653\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t\t\"modelPanel -edit -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels  $panelName;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -camera \\\"|front\\\" \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 16384\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -bluePencil 1\\n    -greasePencils 0\\n    -excludeObjectPreset \\\"All\\\" \\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 1499\\n    -height 653\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t$configName;\n\n            setNamedPanelLayout (localizedPanelLabel(\"Current Layout\"));\n        }\n\n        panelHistory -e -clear mainPanelHistory;\n        sceneUIReplacement -clear;\n\t}\n\n\ngrid -spacing 5 -size 12 -divisions 5 -displayAxes yes -displayGridLines yes -displayDivisionLines yes -displayPerspectiveLabels no -displayOrthographicLabels no -displayAxesBold yes -perspectiveLabelPosition axis -orthographicLabelPosition edge;\nviewManip -drawCompass 0 -compassAngle 0 -frontParameters \"\" -homeParameters \"\" -selectionLockParameters \"\";\n}\n");
	setAttr ".st" 3;
createNode script -n "sceneConfigurationScriptNode";
	rename -uid "80DB217C-4D3D-697B-BD90-C1B14F11E890";
	setAttr ".b" -type "string" "playbackOptions -min 1001 -max 1057 -ast 1001 -aet 1057 ";
	setAttr ".st" 6;
createNode polySphere -n "polySphere1";
	rename -uid "2123A90D-4F3C-23BE-7F80-5FB3F94E370A";
createNode animCurveTL -n "pSphere1_translateX";
	rename -uid "2561624E-49A0-522C-338D-81B87CAD9BF5";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  1001 13.647124510522788 1002 14.67432743066966;
createNode animCurveTL -n "pSphere1_translateY";
	rename -uid "C244E245-471F-7CA6-90EF-059127D42FA7";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr -s 2 ".ktv[0:1]"  1001 11.152488847308941 1002 12.253063404609167;
createNode animCurveTL -n "pSphere1_translateZ";
	rename -uid "FFA1383A-4DC3-0A68-70D0-749A7E7758AF";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr ".ktv[0]"  1001 0;
createNode animCurveTA -n "pSphere1_rotateX";
	rename -uid "432C540E-46FC-3BBF-95E1-0084272DF43F";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr ".ktv[0]"  1001 0;
createNode animCurveTA -n "pSphere1_rotateY";
	rename -uid "C8FFAB7A-41FF-6976-CA2F-E799AB1D288A";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr ".ktv[0]"  1001 0;
createNode animCurveTA -n "pSphere1_rotateZ";
	rename -uid "EA327CAA-488E-1D26-346A-4395FF802E86";
	setAttr ".tan" 2;
	setAttr ".wgt" no;
	setAttr ".ktv[0]"  1001 0;
select -ne :time1;
	setAttr ".o" 1027;
	setAttr ".unw" 1027;
select -ne :hardwareRenderingGlobals;
	setAttr ".otfna" -type "stringArray" 22 "NURBS Curves" "NURBS Surfaces" "Polygons" "Subdiv Surface" "Particles" "Particle Instance" "Fluids" "Strokes" "Image Planes" "UI" "Lights" "Cameras" "Locators" "Joints" "IK Handles" "Deformers" "Motion Trails" "Components" "Hair Systems" "Follicles" "Misc. UI" "Ornaments"  ;
	setAttr ".otfva" -type "Int32Array" 22 0 1 1 1 1 1
		 1 1 1 0 0 0 0 0 0 0 0 0
		 0 0 0 0 ;
	setAttr ".fprt" yes;
	setAttr ".rtfm" 1;
select -ne :renderPartition;
	setAttr -s 2 ".st";
select -ne :renderGlobalsList1;
select -ne :defaultShaderList1;
	setAttr -s 5 ".s";
select -ne :postProcessList1;
	setAttr -s 2 ".p";
select -ne :defaultRenderingList1;
select -ne :standardSurface1;
	setAttr ".bc" -type "float3" 0.40000001 0.40000001 0.40000001 ;
	setAttr ".sr" 0.5;
select -ne :initialShadingGroup;
	setAttr -s 3 ".dsm";
	setAttr ".ro" yes;
select -ne :initialParticleSE;
	setAttr ".ro" yes;
select -ne :defaultRenderGlobals;
	addAttr -ci true -h true -sn "dss" -ln "defaultSurfaceShader" -dt "string";
	setAttr ".ren" -type "string" "arnold";
	setAttr ".dss" -type "string" "standardSurface1";
select -ne :defaultResolution;
	setAttr ".pa" 1;
select -ne :defaultColorMgtGlobals;
	setAttr ".cfe" yes;
	setAttr ".cfp" -type "string" "<MAYA_RESOURCES>/OCIO-configs/Maya2022-default/config.ocio";
	setAttr ".vtn" -type "string" "ACES 1.0 SDR-video (sRGB)";
	setAttr ".vn" -type "string" "ACES 1.0 SDR-video";
	setAttr ".dn" -type "string" "sRGB";
	setAttr ".wsn" -type "string" "ACEScg";
	setAttr ".otn" -type "string" "ACES 1.0 SDR-video (sRGB)";
	setAttr ".potn" -type "string" "ACES 1.0 SDR-video (sRGB)";
select -ne :hardwareRenderGlobals;
	setAttr ".ctrs" 256;
	setAttr ".btrs" 512;
select -ne :ikSystem;
	setAttr -s 4 ".sol";
connectAttr "hair_000_SKL_parentConstraint1.ctx" "hair_000_SKL.tx";
connectAttr "hair_000_SKL_parentConstraint1.cty" "hair_000_SKL.ty";
connectAttr "hair_000_SKL_parentConstraint1.ctz" "hair_000_SKL.tz";
connectAttr "hair_000_SKL_parentConstraint1.crx" "hair_000_SKL.rx";
connectAttr "hair_000_SKL_parentConstraint1.cry" "hair_000_SKL.ry";
connectAttr "hair_000_SKL_parentConstraint1.crz" "hair_000_SKL.rz";
connectAttr "hair_000_SKL.ro" "hair_000_SKL_parentConstraint1.cro";
connectAttr "hair_000_SKL.pim" "hair_000_SKL_parentConstraint1.cpim";
connectAttr "hair_000_SKL.rp" "hair_000_SKL_parentConstraint1.crp";
connectAttr "hair_000_SKL.rpt" "hair_000_SKL_parentConstraint1.crt";
connectAttr "hair_000_SKL.jo" "hair_000_SKL_parentConstraint1.cjo";
connectAttr "hair_000_JNT.t" "hair_000_SKL_parentConstraint1.tg[0].tt";
connectAttr "hair_000_JNT.rp" "hair_000_SKL_parentConstraint1.tg[0].trp";
connectAttr "hair_000_JNT.rpt" "hair_000_SKL_parentConstraint1.tg[0].trt";
connectAttr "hair_000_JNT.r" "hair_000_SKL_parentConstraint1.tg[0].tr";
connectAttr "hair_000_JNT.ro" "hair_000_SKL_parentConstraint1.tg[0].tro";
connectAttr "hair_000_JNT.s" "hair_000_SKL_parentConstraint1.tg[0].ts";
connectAttr "hair_000_JNT.pm" "hair_000_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hair_000_JNT.jo" "hair_000_SKL_parentConstraint1.tg[0].tjo";
connectAttr "hair_000_JNT.ssc" "hair_000_SKL_parentConstraint1.tg[0].tsc";
connectAttr "hair_000_JNT.is" "hair_000_SKL_parentConstraint1.tg[0].tis";
connectAttr "hair_000_SKL_parentConstraint1.w0" "hair_000_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_001_SKL_parentConstraint1.ctx" "hair_001_SKL.tx";
connectAttr "hair_001_SKL_parentConstraint1.cty" "hair_001_SKL.ty";
connectAttr "hair_001_SKL_parentConstraint1.ctz" "hair_001_SKL.tz";
connectAttr "hair_001_SKL_parentConstraint1.crx" "hair_001_SKL.rx";
connectAttr "hair_001_SKL_parentConstraint1.cry" "hair_001_SKL.ry";
connectAttr "hair_001_SKL_parentConstraint1.crz" "hair_001_SKL.rz";
connectAttr "hair_000_SKL.s" "hair_001_SKL.is";
connectAttr "hair_001_SKL.ro" "hair_001_SKL_parentConstraint1.cro";
connectAttr "hair_001_SKL.pim" "hair_001_SKL_parentConstraint1.cpim";
connectAttr "hair_001_SKL.rp" "hair_001_SKL_parentConstraint1.crp";
connectAttr "hair_001_SKL.rpt" "hair_001_SKL_parentConstraint1.crt";
connectAttr "hair_001_SKL.jo" "hair_001_SKL_parentConstraint1.cjo";
connectAttr "hair_001_JNT.t" "hair_001_SKL_parentConstraint1.tg[0].tt";
connectAttr "hair_001_JNT.rp" "hair_001_SKL_parentConstraint1.tg[0].trp";
connectAttr "hair_001_JNT.rpt" "hair_001_SKL_parentConstraint1.tg[0].trt";
connectAttr "hair_001_JNT.r" "hair_001_SKL_parentConstraint1.tg[0].tr";
connectAttr "hair_001_JNT.ro" "hair_001_SKL_parentConstraint1.tg[0].tro";
connectAttr "hair_001_JNT.s" "hair_001_SKL_parentConstraint1.tg[0].ts";
connectAttr "hair_001_JNT.pm" "hair_001_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hair_001_JNT.jo" "hair_001_SKL_parentConstraint1.tg[0].tjo";
connectAttr "hair_001_JNT.ssc" "hair_001_SKL_parentConstraint1.tg[0].tsc";
connectAttr "hair_001_JNT.is" "hair_001_SKL_parentConstraint1.tg[0].tis";
connectAttr "hair_001_SKL_parentConstraint1.w0" "hair_001_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_002_SKL_parentConstraint1.ctx" "hair_002_SKL.tx";
connectAttr "hair_002_SKL_parentConstraint1.cty" "hair_002_SKL.ty";
connectAttr "hair_002_SKL_parentConstraint1.ctz" "hair_002_SKL.tz";
connectAttr "hair_002_SKL_parentConstraint1.crx" "hair_002_SKL.rx";
connectAttr "hair_002_SKL_parentConstraint1.cry" "hair_002_SKL.ry";
connectAttr "hair_002_SKL_parentConstraint1.crz" "hair_002_SKL.rz";
connectAttr "hair_001_SKL.s" "hair_002_SKL.is";
connectAttr "hair_002_SKL.ro" "hair_002_SKL_parentConstraint1.cro";
connectAttr "hair_002_SKL.pim" "hair_002_SKL_parentConstraint1.cpim";
connectAttr "hair_002_SKL.rp" "hair_002_SKL_parentConstraint1.crp";
connectAttr "hair_002_SKL.rpt" "hair_002_SKL_parentConstraint1.crt";
connectAttr "hair_002_SKL.jo" "hair_002_SKL_parentConstraint1.cjo";
connectAttr "hair_002_JNT.t" "hair_002_SKL_parentConstraint1.tg[0].tt";
connectAttr "hair_002_JNT.rp" "hair_002_SKL_parentConstraint1.tg[0].trp";
connectAttr "hair_002_JNT.rpt" "hair_002_SKL_parentConstraint1.tg[0].trt";
connectAttr "hair_002_JNT.r" "hair_002_SKL_parentConstraint1.tg[0].tr";
connectAttr "hair_002_JNT.ro" "hair_002_SKL_parentConstraint1.tg[0].tro";
connectAttr "hair_002_JNT.s" "hair_002_SKL_parentConstraint1.tg[0].ts";
connectAttr "hair_002_JNT.pm" "hair_002_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hair_002_JNT.jo" "hair_002_SKL_parentConstraint1.tg[0].tjo";
connectAttr "hair_002_JNT.ssc" "hair_002_SKL_parentConstraint1.tg[0].tsc";
connectAttr "hair_002_JNT.is" "hair_002_SKL_parentConstraint1.tg[0].tis";
connectAttr "hair_002_SKL_parentConstraint1.w0" "hair_002_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_003_SKL_parentConstraint1.ctx" "hair_003_SKL.tx";
connectAttr "hair_003_SKL_parentConstraint1.cty" "hair_003_SKL.ty";
connectAttr "hair_003_SKL_parentConstraint1.ctz" "hair_003_SKL.tz";
connectAttr "hair_003_SKL_parentConstraint1.crx" "hair_003_SKL.rx";
connectAttr "hair_003_SKL_parentConstraint1.cry" "hair_003_SKL.ry";
connectAttr "hair_003_SKL_parentConstraint1.crz" "hair_003_SKL.rz";
connectAttr "hair_002_SKL.s" "hair_003_SKL.is";
connectAttr "hair_003_SKL.ro" "hair_003_SKL_parentConstraint1.cro";
connectAttr "hair_003_SKL.pim" "hair_003_SKL_parentConstraint1.cpim";
connectAttr "hair_003_SKL.rp" "hair_003_SKL_parentConstraint1.crp";
connectAttr "hair_003_SKL.rpt" "hair_003_SKL_parentConstraint1.crt";
connectAttr "hair_003_SKL.jo" "hair_003_SKL_parentConstraint1.cjo";
connectAttr "hair_003_JNT.t" "hair_003_SKL_parentConstraint1.tg[0].tt";
connectAttr "hair_003_JNT.rp" "hair_003_SKL_parentConstraint1.tg[0].trp";
connectAttr "hair_003_JNT.rpt" "hair_003_SKL_parentConstraint1.tg[0].trt";
connectAttr "hair_003_JNT.r" "hair_003_SKL_parentConstraint1.tg[0].tr";
connectAttr "hair_003_JNT.ro" "hair_003_SKL_parentConstraint1.tg[0].tro";
connectAttr "hair_003_JNT.s" "hair_003_SKL_parentConstraint1.tg[0].ts";
connectAttr "hair_003_JNT.pm" "hair_003_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hair_003_JNT.jo" "hair_003_SKL_parentConstraint1.tg[0].tjo";
connectAttr "hair_003_JNT.ssc" "hair_003_SKL_parentConstraint1.tg[0].tsc";
connectAttr "hair_003_JNT.is" "hair_003_SKL_parentConstraint1.tg[0].tis";
connectAttr "hair_003_SKL_parentConstraint1.w0" "hair_003_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_004_SKL_parentConstraint1.ctx" "hair_004_SKL.tx";
connectAttr "hair_004_SKL_parentConstraint1.cty" "hair_004_SKL.ty";
connectAttr "hair_004_SKL_parentConstraint1.ctz" "hair_004_SKL.tz";
connectAttr "hair_004_SKL_parentConstraint1.crx" "hair_004_SKL.rx";
connectAttr "hair_004_SKL_parentConstraint1.cry" "hair_004_SKL.ry";
connectAttr "hair_004_SKL_parentConstraint1.crz" "hair_004_SKL.rz";
connectAttr "hair_003_SKL.s" "hair_004_SKL.is";
connectAttr "hair_004_SKL.ro" "hair_004_SKL_parentConstraint1.cro";
connectAttr "hair_004_SKL.pim" "hair_004_SKL_parentConstraint1.cpim";
connectAttr "hair_004_SKL.rp" "hair_004_SKL_parentConstraint1.crp";
connectAttr "hair_004_SKL.rpt" "hair_004_SKL_parentConstraint1.crt";
connectAttr "hair_004_SKL.jo" "hair_004_SKL_parentConstraint1.cjo";
connectAttr "hair_004_JNT.t" "hair_004_SKL_parentConstraint1.tg[0].tt";
connectAttr "hair_004_JNT.rp" "hair_004_SKL_parentConstraint1.tg[0].trp";
connectAttr "hair_004_JNT.rpt" "hair_004_SKL_parentConstraint1.tg[0].trt";
connectAttr "hair_004_JNT.r" "hair_004_SKL_parentConstraint1.tg[0].tr";
connectAttr "hair_004_JNT.ro" "hair_004_SKL_parentConstraint1.tg[0].tro";
connectAttr "hair_004_JNT.s" "hair_004_SKL_parentConstraint1.tg[0].ts";
connectAttr "hair_004_JNT.pm" "hair_004_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hair_004_JNT.jo" "hair_004_SKL_parentConstraint1.tg[0].tjo";
connectAttr "hair_004_JNT.ssc" "hair_004_SKL_parentConstraint1.tg[0].tsc";
connectAttr "hair_004_JNT.is" "hair_004_SKL_parentConstraint1.tg[0].tis";
connectAttr "hair_004_SKL_parentConstraint1.w0" "hair_004_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_005_SKL_parentConstraint1.ctx" "hair_005_SKL.tx";
connectAttr "hair_005_SKL_parentConstraint1.cty" "hair_005_SKL.ty";
connectAttr "hair_005_SKL_parentConstraint1.ctz" "hair_005_SKL.tz";
connectAttr "hair_005_SKL_parentConstraint1.crx" "hair_005_SKL.rx";
connectAttr "hair_005_SKL_parentConstraint1.cry" "hair_005_SKL.ry";
connectAttr "hair_005_SKL_parentConstraint1.crz" "hair_005_SKL.rz";
connectAttr "hair_004_SKL.s" "hair_005_SKL.is";
connectAttr "hair_005_SKL.ro" "hair_005_SKL_parentConstraint1.cro";
connectAttr "hair_005_SKL.pim" "hair_005_SKL_parentConstraint1.cpim";
connectAttr "hair_005_SKL.rp" "hair_005_SKL_parentConstraint1.crp";
connectAttr "hair_005_SKL.rpt" "hair_005_SKL_parentConstraint1.crt";
connectAttr "hair_005_SKL.jo" "hair_005_SKL_parentConstraint1.cjo";
connectAttr "hair_005_JNT.t" "hair_005_SKL_parentConstraint1.tg[0].tt";
connectAttr "hair_005_JNT.rp" "hair_005_SKL_parentConstraint1.tg[0].trp";
connectAttr "hair_005_JNT.rpt" "hair_005_SKL_parentConstraint1.tg[0].trt";
connectAttr "hair_005_JNT.r" "hair_005_SKL_parentConstraint1.tg[0].tr";
connectAttr "hair_005_JNT.ro" "hair_005_SKL_parentConstraint1.tg[0].tro";
connectAttr "hair_005_JNT.s" "hair_005_SKL_parentConstraint1.tg[0].ts";
connectAttr "hair_005_JNT.pm" "hair_005_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hair_005_JNT.jo" "hair_005_SKL_parentConstraint1.tg[0].tjo";
connectAttr "hair_005_JNT.ssc" "hair_005_SKL_parentConstraint1.tg[0].tsc";
connectAttr "hair_005_JNT.is" "hair_005_SKL_parentConstraint1.tg[0].tis";
connectAttr "hair_005_SKL_parentConstraint1.w0" "hair_005_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_CTL000_GRP_parentConstraint1.ctx" "hair_CTL000_GRP.tx";
connectAttr "hair_CTL000_GRP_parentConstraint1.cty" "hair_CTL000_GRP.ty";
connectAttr "hair_CTL000_GRP_parentConstraint1.ctz" "hair_CTL000_GRP.tz";
connectAttr "hair_CTL000_GRP_parentConstraint1.crx" "hair_CTL000_GRP.rx";
connectAttr "hair_CTL000_GRP_parentConstraint1.cry" "hair_CTL000_GRP.ry";
connectAttr "hair_CTL000_GRP_parentConstraint1.crz" "hair_CTL000_GRP.rz";
connectAttr "hairCOG_CTL.globalScale" "hair_CTL000_GRP.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_CTL000_GRP.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_CTL000_GRP.sz";
connectAttr "hairExtraTwist000_ADL.o" "hairBtm_CTL.twist" -l on;
connectAttr "hair_CTL000_GRP.ro" "hair_CTL000_GRP_parentConstraint1.cro";
connectAttr "hair_CTL000_GRP.pim" "hair_CTL000_GRP_parentConstraint1.cpim";
connectAttr "hair_CTL000_GRP.rp" "hair_CTL000_GRP_parentConstraint1.crp";
connectAttr "hair_CTL000_GRP.rpt" "hair_CTL000_GRP_parentConstraint1.crt";
connectAttr "hairCOG_Btm_CTL.t" "hair_CTL000_GRP_parentConstraint1.tg[0].tt";
connectAttr "hairCOG_Btm_CTL.rp" "hair_CTL000_GRP_parentConstraint1.tg[0].trp";
connectAttr "hairCOG_Btm_CTL.rpt" "hair_CTL000_GRP_parentConstraint1.tg[0].trt";
connectAttr "hairCOG_Btm_CTL.r" "hair_CTL000_GRP_parentConstraint1.tg[0].tr";
connectAttr "hairCOG_Btm_CTL.ro" "hair_CTL000_GRP_parentConstraint1.tg[0].tro";
connectAttr "hairCOG_Btm_CTL.s" "hair_CTL000_GRP_parentConstraint1.tg[0].ts";
connectAttr "hairCOG_Btm_CTL.pm" "hair_CTL000_GRP_parentConstraint1.tg[0].tpm";
connectAttr "hair_CTL000_GRP_parentConstraint1.w0" "hair_CTL000_GRP_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_CTL002_GRP_parentConstraint1.ctx" "hair_CTL002_GRP.tx";
connectAttr "hair_CTL002_GRP_parentConstraint1.cty" "hair_CTL002_GRP.ty";
connectAttr "hair_CTL002_GRP_parentConstraint1.ctz" "hair_CTL002_GRP.tz";
connectAttr "hair_CTL002_GRP_parentConstraint1.crx" "hair_CTL002_GRP.rx";
connectAttr "hair_CTL002_GRP_parentConstraint1.cry" "hair_CTL002_GRP.ry";
connectAttr "hair_CTL002_GRP_parentConstraint1.crz" "hair_CTL002_GRP.rz";
connectAttr "hairCOG_CTL.globalScale" "hair_CTL002_GRP.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_CTL002_GRP.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_CTL002_GRP.sz";
connectAttr "hairExtraTwist002_ADL.o" "hairTop_CTL.twist" -l on;
connectAttr "hair_CTL002_GRP.ro" "hair_CTL002_GRP_parentConstraint1.cro";
connectAttr "hair_CTL002_GRP.pim" "hair_CTL002_GRP_parentConstraint1.cpim";
connectAttr "hair_CTL002_GRP.rp" "hair_CTL002_GRP_parentConstraint1.crp";
connectAttr "hair_CTL002_GRP.rpt" "hair_CTL002_GRP_parentConstraint1.crt";
connectAttr "hair_CTL002constraint_GRP.t" "hair_CTL002_GRP_parentConstraint1.tg[0].tt"
		;
connectAttr "hair_CTL002constraint_GRP.rp" "hair_CTL002_GRP_parentConstraint1.tg[0].trp"
		;
connectAttr "hair_CTL002constraint_GRP.rpt" "hair_CTL002_GRP_parentConstraint1.tg[0].trt"
		;
connectAttr "hair_CTL002constraint_GRP.r" "hair_CTL002_GRP_parentConstraint1.tg[0].tr"
		;
connectAttr "hair_CTL002constraint_GRP.ro" "hair_CTL002_GRP_parentConstraint1.tg[0].tro"
		;
connectAttr "hair_CTL002constraint_GRP.s" "hair_CTL002_GRP_parentConstraint1.tg[0].ts"
		;
connectAttr "hair_CTL002constraint_GRP.pm" "hair_CTL002_GRP_parentConstraint1.tg[0].tpm"
		;
connectAttr "hair_CTL002_GRP_parentConstraint1.w0" "hair_CTL002_GRP_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_All001_GRP_parentConstraint1.ctx" "hair_All001_GRP.tx";
connectAttr "hair_All001_GRP_parentConstraint1.cty" "hair_All001_GRP.ty";
connectAttr "hair_All001_GRP_parentConstraint1.ctz" "hair_All001_GRP.tz";
connectAttr "hair_All001_GRP_parentConstraint1.crx" "hair_All001_GRP.rx";
connectAttr "hair_All001_GRP_parentConstraint1.cry" "hair_All001_GRP.ry";
connectAttr "hair_All001_GRP_parentConstraint1.crz" "hair_All001_GRP.rz";
connectAttr "hairCOG_CTL.globalScale" "hair_All001_GRP.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_All001_GRP.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_All001_GRP.sz";
connectAttr "hairCOG_CTL.subControlOneVisibility" "hairCOG_Mid_CTL.v" -l on;
connectAttr "hair_All001_GRP.ro" "hair_All001_GRP_parentConstraint1.cro";
connectAttr "hair_All001_GRP.pim" "hair_All001_GRP_parentConstraint1.cpim";
connectAttr "hair_All001_GRP.rp" "hair_All001_GRP_parentConstraint1.crp";
connectAttr "hair_All001_GRP.rpt" "hair_All001_GRP_parentConstraint1.crt";
connectAttr "hairCOG_CTL.t" "hair_All001_GRP_parentConstraint1.tg[0].tt";
connectAttr "hairCOG_CTL.rp" "hair_All001_GRP_parentConstraint1.tg[0].trp";
connectAttr "hairCOG_CTL.rpt" "hair_All001_GRP_parentConstraint1.tg[0].trt";
connectAttr "hairCOG_CTL.r" "hair_All001_GRP_parentConstraint1.tg[0].tr";
connectAttr "hairCOG_CTL.ro" "hair_All001_GRP_parentConstraint1.tg[0].tro";
connectAttr "hairCOG_CTL.s" "hair_All001_GRP_parentConstraint1.tg[0].ts";
connectAttr "hairCOG_CTL.pm" "hair_All001_GRP_parentConstraint1.tg[0].tpm";
connectAttr "hair_All001_GRP_parentConstraint1.w0" "hair_All001_GRP_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_All002_GRP_parentConstraint1.ctx" "hair_All002_GRP.tx";
connectAttr "hair_All002_GRP_parentConstraint1.cty" "hair_All002_GRP.ty";
connectAttr "hair_All002_GRP_parentConstraint1.ctz" "hair_All002_GRP.tz";
connectAttr "hair_All002_GRP_parentConstraint1.crx" "hair_All002_GRP.rx";
connectAttr "hair_All002_GRP_parentConstraint1.cry" "hair_All002_GRP.ry";
connectAttr "hair_All002_GRP_parentConstraint1.crz" "hair_All002_GRP.rz";
connectAttr "hairCOG_CTL.globalScale" "hair_All002_GRP.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_All002_GRP.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_All002_GRP.sz";
connectAttr "hairCOG_CTL.subControlTwoVisibility" "hairCOG_Btm_CTL.v" -l on;
connectAttr "hair_All002_GRP.ro" "hair_All002_GRP_parentConstraint1.cro";
connectAttr "hair_All002_GRP.pim" "hair_All002_GRP_parentConstraint1.cpim";
connectAttr "hair_All002_GRP.rp" "hair_All002_GRP_parentConstraint1.crp";
connectAttr "hair_All002_GRP.rpt" "hair_All002_GRP_parentConstraint1.crt";
connectAttr "hairCOG_Mid_CTL.t" "hair_All002_GRP_parentConstraint1.tg[0].tt";
connectAttr "hairCOG_Mid_CTL.rp" "hair_All002_GRP_parentConstraint1.tg[0].trp";
connectAttr "hairCOG_Mid_CTL.rpt" "hair_All002_GRP_parentConstraint1.tg[0].trt";
connectAttr "hairCOG_Mid_CTL.r" "hair_All002_GRP_parentConstraint1.tg[0].tr";
connectAttr "hairCOG_Mid_CTL.ro" "hair_All002_GRP_parentConstraint1.tg[0].tro";
connectAttr "hairCOG_Mid_CTL.s" "hair_All002_GRP_parentConstraint1.tg[0].ts";
connectAttr "hairCOG_Mid_CTL.pm" "hair_All002_GRP_parentConstraint1.tg[0].tpm";
connectAttr "hair_All002_GRP_parentConstraint1.w0" "hair_All002_GRP_parentConstraint1.tg[0].tw"
		;
connectAttr "hairCOG_CTL.globalScale" "hair_All000_GRP.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_All000_GRP.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_All000_GRP.sz";
connectAttr "hair_000_FK.msg" "hair_000_IKH.hsj";
connectAttr "hair_000_EFF.hp" "hair_000_IKH.hee";
connectAttr "ikSplineSolver.msg" "hair_000_IKH.hsv";
connectAttr "hair_000_CRVShape.ws" "hair_000_IKH.ic";
connectAttr "hair_SquashStretch000_MDN.ox" "hair_000_FK.sx";
connectAttr "hair_000_FK.s" "hair_001_FK.is";
connectAttr "hair_SquashStretch000_MDN.ox" "hair_001_FK.sx";
connectAttr "hair_001_FK.s" "hair_002_FK.is";
connectAttr "hair_SquashStretch000_MDN.ox" "hair_002_FK.sx";
connectAttr "hair_002_FK.s" "hair_003_FK.is";
connectAttr "hair_SquashStretch000_MDN.ox" "hair_003_FK.sx";
connectAttr "hair_003_FK.s" "hair_004_FK.is";
connectAttr "hair_SquashStretch000_MDN.ox" "hair_004_FK.sx";
connectAttr "hair_004_FK.s" "hair_005_FK.is";
connectAttr "hair_SquashStretch000_MDN.ox" "hair_005_FK.sx";
connectAttr "hair_005_FK.s" "hair_005_JNT.is";
connectAttr "unitConversion12.o" "hair_005_JNT.rx";
connectAttr "hair_005_FK.tx" "hair_000_EFF.tx";
connectAttr "hair_005_FK.ty" "hair_000_EFF.ty";
connectAttr "hair_005_FK.tz" "hair_000_EFF.tz";
connectAttr "hair_005_FK.opm" "hair_000_EFF.opm";
connectAttr "hair_004_FK.s" "hair_004_JNT.is";
connectAttr "unitConversion11.o" "hair_004_JNT.rx";
connectAttr "hair_003_FK.s" "hair_003_JNT.is";
connectAttr "unitConversion10.o" "hair_003_JNT.rx";
connectAttr "hair_002_FK.s" "hair_002_JNT.is";
connectAttr "unitConversion9.o" "hair_002_JNT.rx";
connectAttr "hair_001_FK.s" "hair_001_JNT.is";
connectAttr "unitConversion8.o" "hair_001_JNT.rx";
connectAttr "hair_000_FK.s" "hair_000_JNT.is";
connectAttr "unitConversion7.o" "hair_000_JNT.rx";
connectAttr "hair_Joint_000_FOLShape.ot" "hair_Joint_000_FOL.t";
connectAttr "hair_Joint_000_FOLShape.or" "hair_Joint_000_FOL.r";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_000_FOL.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_000_FOL.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_000_FOL.sz";
connectAttr "hair_001_GEOShape.wm" "hair_Joint_000_FOLShape.iwm";
connectAttr "hair_001_GEOShape.l" "hair_Joint_000_FOLShape.is";
connectAttr "hair_Joint_001_FOLShape.ot" "hair_Joint_001_FOL.t";
connectAttr "hair_Joint_001_FOLShape.or" "hair_Joint_001_FOL.r";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_001_FOL.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_001_FOL.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_001_FOL.sz";
connectAttr "hair_001_GEOShape.wm" "hair_Joint_001_FOLShape.iwm";
connectAttr "hair_001_GEOShape.l" "hair_Joint_001_FOLShape.is";
connectAttr "hair_Joint_002_FOLShape.ot" "hair_Joint_002_FOL.t";
connectAttr "hair_Joint_002_FOLShape.or" "hair_Joint_002_FOL.r";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_002_FOL.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_002_FOL.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_002_FOL.sz";
connectAttr "hair_001_GEOShape.wm" "hair_Joint_002_FOLShape.iwm";
connectAttr "hair_001_GEOShape.l" "hair_Joint_002_FOLShape.is";
connectAttr "hair_Joint_003_FOLShape.ot" "hair_Joint_003_FOL.t";
connectAttr "hair_Joint_003_FOLShape.or" "hair_Joint_003_FOL.r";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_003_FOL.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_003_FOL.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_003_FOL.sz";
connectAttr "hair_001_GEOShape.wm" "hair_Joint_003_FOLShape.iwm";
connectAttr "hair_001_GEOShape.l" "hair_Joint_003_FOLShape.is";
connectAttr "hair_Joint_004_FOLShape.ot" "hair_Joint_004_FOL.t";
connectAttr "hair_Joint_004_FOLShape.or" "hair_Joint_004_FOL.r";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_004_FOL.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_004_FOL.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_004_FOL.sz";
connectAttr "hair_001_GEOShape.wm" "hair_Joint_004_FOLShape.iwm";
connectAttr "hair_001_GEOShape.l" "hair_Joint_004_FOLShape.is";
connectAttr "hair_Joint_005_FOLShape.ot" "hair_Joint_005_FOL.t";
connectAttr "hair_Joint_005_FOLShape.or" "hair_Joint_005_FOL.r";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_005_FOL.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_005_FOL.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Joint_005_FOL.sz";
connectAttr "hair_001_GEOShape.wm" "hair_Joint_005_FOLShape.iwm";
connectAttr "hair_001_GEOShape.l" "hair_Joint_005_FOLShape.is";
connectAttr "hair_Mid000_FOLShape.ot" "hair_Mid000_FOL.t";
connectAttr "hair_Mid000_FOLShape.or" "hair_Mid000_FOL.r";
connectAttr "hairCOG_CTL.globalScale" "hair_Mid000_FOL.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Mid000_FOL.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Mid000_FOL.sz";
connectAttr "hair_000_GEOShape.wm" "hair_Mid000_FOLShape.iwm";
connectAttr "hair_000_GEOShape.l" "hair_Mid000_FOLShape.is";
connectAttr "hair_CTL001_TopSDK_GRP_rotateZ.o" "hair_CTL001_TopSDK_GRP.rz";
connectAttr "hair_CTL001_TopRotateSDK_GRP_rotateZ.o" "hair_CTL001_TopRotateSDK_GRP.rz"
		;
connectAttr "hair_CTL001_BtmRotateSDK_GRP_rotateZ.o" "hair_CTL001_BtmRotateSDK_GRP.rz"
		;
connectAttr "hair_CTL001_BtmSDK_GRP_rotateZ.o" "hair_CTL001_BtmSDK_GRP.rz";
connectAttr "hair_Geo000_FK_parentConstraint1.ctx" "hair_Geo000_FK.tx";
connectAttr "hair_Geo000_FK_parentConstraint1.cty" "hair_Geo000_FK.ty";
connectAttr "hair_Geo000_FK_parentConstraint1.ctz" "hair_Geo000_FK.tz";
connectAttr "hair_Geo000_FK_parentConstraint1.crx" "hair_Geo000_FK.rx";
connectAttr "hair_Geo000_FK_parentConstraint1.cry" "hair_Geo000_FK.ry";
connectAttr "hair_Geo000_FK_parentConstraint1.crz" "hair_Geo000_FK.rz";
connectAttr "hairCOG_CTL.globalScale" "hair_Geo000_FK.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Geo000_FK.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Geo000_FK.sz";
connectAttr "hair_Geo000_FK.ro" "hair_Geo000_FK_parentConstraint1.cro";
connectAttr "hair_Geo000_FK.pim" "hair_Geo000_FK_parentConstraint1.cpim";
connectAttr "hair_Geo000_FK.rp" "hair_Geo000_FK_parentConstraint1.crp";
connectAttr "hair_Geo000_FK.rpt" "hair_Geo000_FK_parentConstraint1.crt";
connectAttr "hair_Geo000_FK.jo" "hair_Geo000_FK_parentConstraint1.cjo";
connectAttr "hairBtm_CTL.t" "hair_Geo000_FK_parentConstraint1.tg[0].tt";
connectAttr "hairBtm_CTL.rp" "hair_Geo000_FK_parentConstraint1.tg[0].trp";
connectAttr "hairBtm_CTL.rpt" "hair_Geo000_FK_parentConstraint1.tg[0].trt";
connectAttr "hairBtm_CTL.r" "hair_Geo000_FK_parentConstraint1.tg[0].tr";
connectAttr "hairBtm_CTL.ro" "hair_Geo000_FK_parentConstraint1.tg[0].tro";
connectAttr "hairBtm_CTL.s" "hair_Geo000_FK_parentConstraint1.tg[0].ts";
connectAttr "hairBtm_CTL.pm" "hair_Geo000_FK_parentConstraint1.tg[0].tpm";
connectAttr "hair_Geo000_FK_parentConstraint1.w0" "hair_Geo000_FK_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_Geo001_FK_parentConstraint1.ctx" "hair_Geo001_FK.tx";
connectAttr "hair_Geo001_FK_parentConstraint1.cty" "hair_Geo001_FK.ty";
connectAttr "hair_Geo001_FK_parentConstraint1.ctz" "hair_Geo001_FK.tz";
connectAttr "hair_Geo001_FK_parentConstraint1.crx" "hair_Geo001_FK.rx";
connectAttr "hair_Geo001_FK_parentConstraint1.cry" "hair_Geo001_FK.ry";
connectAttr "hair_Geo001_FK_parentConstraint1.crz" "hair_Geo001_FK.rz";
connectAttr "hairCOG_CTL.globalScale" "hair_Geo001_FK.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Geo001_FK.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Geo001_FK.sz";
connectAttr "hair_Geo001_FK.ro" "hair_Geo001_FK_parentConstraint1.cro";
connectAttr "hair_Geo001_FK.pim" "hair_Geo001_FK_parentConstraint1.cpim";
connectAttr "hair_Geo001_FK.rp" "hair_Geo001_FK_parentConstraint1.crp";
connectAttr "hair_Geo001_FK.rpt" "hair_Geo001_FK_parentConstraint1.crt";
connectAttr "hair_Geo001_FK.jo" "hair_Geo001_FK_parentConstraint1.cjo";
connectAttr "hairMid_CTL.t" "hair_Geo001_FK_parentConstraint1.tg[0].tt";
connectAttr "hairMid_CTL.rp" "hair_Geo001_FK_parentConstraint1.tg[0].trp";
connectAttr "hairMid_CTL.rpt" "hair_Geo001_FK_parentConstraint1.tg[0].trt";
connectAttr "hairMid_CTL.r" "hair_Geo001_FK_parentConstraint1.tg[0].tr";
connectAttr "hairMid_CTL.ro" "hair_Geo001_FK_parentConstraint1.tg[0].tro";
connectAttr "hairMid_CTL.s" "hair_Geo001_FK_parentConstraint1.tg[0].ts";
connectAttr "hairMid_CTL.pm" "hair_Geo001_FK_parentConstraint1.tg[0].tpm";
connectAttr "hair_Geo001_FK_parentConstraint1.w0" "hair_Geo001_FK_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_Geo002_FK_parentConstraint1.ctx" "hair_Geo002_FK.tx";
connectAttr "hair_Geo002_FK_parentConstraint1.cty" "hair_Geo002_FK.ty";
connectAttr "hair_Geo002_FK_parentConstraint1.ctz" "hair_Geo002_FK.tz";
connectAttr "hair_Geo002_FK_parentConstraint1.crx" "hair_Geo002_FK.rx";
connectAttr "hair_Geo002_FK_parentConstraint1.cry" "hair_Geo002_FK.ry";
connectAttr "hair_Geo002_FK_parentConstraint1.crz" "hair_Geo002_FK.rz";
connectAttr "hairCOG_CTL.globalScale" "hair_Geo002_FK.sx";
connectAttr "hairCOG_CTL.globalScale" "hair_Geo002_FK.sy";
connectAttr "hairCOG_CTL.globalScale" "hair_Geo002_FK.sz";
connectAttr "hair_Geo002_FK.ro" "hair_Geo002_FK_parentConstraint1.cro";
connectAttr "hair_Geo002_FK.pim" "hair_Geo002_FK_parentConstraint1.cpim";
connectAttr "hair_Geo002_FK.rp" "hair_Geo002_FK_parentConstraint1.crp";
connectAttr "hair_Geo002_FK.rpt" "hair_Geo002_FK_parentConstraint1.crt";
connectAttr "hair_Geo002_FK.jo" "hair_Geo002_FK_parentConstraint1.cjo";
connectAttr "hairTop_CTL.t" "hair_Geo002_FK_parentConstraint1.tg[0].tt";
connectAttr "hairTop_CTL.rp" "hair_Geo002_FK_parentConstraint1.tg[0].trp";
connectAttr "hairTop_CTL.rpt" "hair_Geo002_FK_parentConstraint1.tg[0].trt";
connectAttr "hairTop_CTL.r" "hair_Geo002_FK_parentConstraint1.tg[0].tr";
connectAttr "hairTop_CTL.ro" "hair_Geo002_FK_parentConstraint1.tg[0].tro";
connectAttr "hairTop_CTL.s" "hair_Geo002_FK_parentConstraint1.tg[0].ts";
connectAttr "hairTop_CTL.pm" "hair_Geo002_FK_parentConstraint1.tg[0].tpm";
connectAttr "hair_Geo002_FK_parentConstraint1.w0" "hair_Geo002_FK_parentConstraint1.tg[0].tw"
		;
connectAttr "hair_Geo000_SKN.og[0]" "hair_000_GEOShape.cr";
connectAttr "tweak1.pl[0].cp[0]" "hair_000_GEOShape.twl";
connectAttr "hair_Geo001_SKN.og[0]" "hair_001_GEOShape.cr";
connectAttr "tweak2.pl[0].cp[0]" "hair_001_GEOShape.twl";
connectAttr "hair_Crv000_SKN.og[0]" "hair_000_CRVShape.cr";
connectAttr "tweak3.pl[0].cp[0]" "hair_000_CRVShape.twl";
connectAttr "hairTip_002_GRP_parentConstraint1.ctx" "hairTip_002_GRP.tx";
connectAttr "hairTip_002_GRP_parentConstraint1.cty" "hairTip_002_GRP.ty";
connectAttr "hairTip_002_GRP_parentConstraint1.ctz" "hairTip_002_GRP.tz";
connectAttr "hairTip_002_GRP_parentConstraint1.crz" "hairTip_002_GRP.rz";
connectAttr "hairTip_002_GRP_parentConstraint1.cry" "hairTip_002_GRP.ry";
connectAttr "hairTip_002_GRP_parentConstraint1.crx" "hairTip_002_GRP.rx";
connectAttr "hairTip_002_GRP.ro" "hairTip_002_GRP_parentConstraint1.cro";
connectAttr "hairTip_002_GRP.pim" "hairTip_002_GRP_parentConstraint1.cpim";
connectAttr "hairTip_002_GRP.rp" "hairTip_002_GRP_parentConstraint1.crp";
connectAttr "hairTip_002_GRP.rpt" "hairTip_002_GRP_parentConstraint1.crt";
connectAttr "hairTip_001_CTL.t" "hairTip_002_GRP_parentConstraint1.tg[0].tt";
connectAttr "hairTip_001_CTL.rp" "hairTip_002_GRP_parentConstraint1.tg[0].trp";
connectAttr "hairTip_001_CTL.rpt" "hairTip_002_GRP_parentConstraint1.tg[0].trt";
connectAttr "hairTip_001_CTL.r" "hairTip_002_GRP_parentConstraint1.tg[0].tr";
connectAttr "hairTip_001_CTL.ro" "hairTip_002_GRP_parentConstraint1.tg[0].tro";
connectAttr "hairTip_001_CTL.s" "hairTip_002_GRP_parentConstraint1.tg[0].ts";
connectAttr "hairTip_001_CTL.pm" "hairTip_002_GRP_parentConstraint1.tg[0].tpm";
connectAttr "hairTip_002_GRP_parentConstraint1.w0" "hairTip_002_GRP_parentConstraint1.tg[0].tw"
		;
connectAttr "hairTip_004_GRP_parentConstraint1.ctx" "hairTip_004_GRP.tx";
connectAttr "hairTip_004_GRP_parentConstraint1.cty" "hairTip_004_GRP.ty";
connectAttr "hairTip_004_GRP_parentConstraint1.ctz" "hairTip_004_GRP.tz";
connectAttr "hairTip_004_GRP_parentConstraint1.crz" "hairTip_004_GRP.rz";
connectAttr "hairTip_004_GRP_parentConstraint1.cry" "hairTip_004_GRP.ry";
connectAttr "hairTip_004_GRP_parentConstraint1.crx" "hairTip_004_GRP.rx";
connectAttr "hairTip_004_GRP.ro" "hairTip_004_GRP_parentConstraint1.cro";
connectAttr "hairTip_004_GRP.pim" "hairTip_004_GRP_parentConstraint1.cpim";
connectAttr "hairTip_004_GRP.rp" "hairTip_004_GRP_parentConstraint1.crp";
connectAttr "hairTip_004_GRP.rpt" "hairTip_004_GRP_parentConstraint1.crt";
connectAttr "hairTip_003_CTL.t" "hairTip_004_GRP_parentConstraint1.tg[0].tt";
connectAttr "hairTip_003_CTL.rp" "hairTip_004_GRP_parentConstraint1.tg[0].trp";
connectAttr "hairTip_003_CTL.rpt" "hairTip_004_GRP_parentConstraint1.tg[0].trt";
connectAttr "hairTip_003_CTL.r" "hairTip_004_GRP_parentConstraint1.tg[0].tr";
connectAttr "hairTip_003_CTL.ro" "hairTip_004_GRP_parentConstraint1.tg[0].tro";
connectAttr "hairTip_003_CTL.s" "hairTip_004_GRP_parentConstraint1.tg[0].ts";
connectAttr "hairTip_003_CTL.pm" "hairTip_004_GRP_parentConstraint1.tg[0].tpm";
connectAttr "hairTip_004_GRP_parentConstraint1.w0" "hairTip_004_GRP_parentConstraint1.tg[0].tw"
		;
connectAttr "hairTip_001_GRP_parentConstraint1.ctx" "hairTip_001_GRP.tx";
connectAttr "hairTip_001_GRP_parentConstraint1.cty" "hairTip_001_GRP.ty";
connectAttr "hairTip_001_GRP_parentConstraint1.ctz" "hairTip_001_GRP.tz";
connectAttr "hairTip_001_GRP_parentConstraint1.crz" "hairTip_001_GRP.rz";
connectAttr "hairTip_001_GRP_parentConstraint1.cry" "hairTip_001_GRP.ry";
connectAttr "hairTip_001_GRP_parentConstraint1.crx" "hairTip_001_GRP.rx";
connectAttr "hairTip_001_GRP.ro" "hairTip_001_GRP_parentConstraint1.cro";
connectAttr "hairTip_001_GRP.pim" "hairTip_001_GRP_parentConstraint1.cpim";
connectAttr "hairTip_001_GRP.rp" "hairTip_001_GRP_parentConstraint1.crp";
connectAttr "hairTip_001_GRP.rpt" "hairTip_001_GRP_parentConstraint1.crt";
connectAttr "hairTop_CTL.t" "hairTip_001_GRP_parentConstraint1.tg[0].tt";
connectAttr "hairTop_CTL.rp" "hairTip_001_GRP_parentConstraint1.tg[0].trp";
connectAttr "hairTop_CTL.rpt" "hairTip_001_GRP_parentConstraint1.tg[0].trt";
connectAttr "hairTop_CTL.r" "hairTip_001_GRP_parentConstraint1.tg[0].tr";
connectAttr "hairTop_CTL.ro" "hairTip_001_GRP_parentConstraint1.tg[0].tro";
connectAttr "hairTop_CTL.s" "hairTip_001_GRP_parentConstraint1.tg[0].ts";
connectAttr "hairTop_CTL.pm" "hairTip_001_GRP_parentConstraint1.tg[0].tpm";
connectAttr "hairTip_001_GRP_parentConstraint1.w0" "hairTip_001_GRP_parentConstraint1.tg[0].tw"
		;
connectAttr "hairTip_003_GRP_parentConstraint1.ctx" "hairTip_003_GRP.tx";
connectAttr "hairTip_003_GRP_parentConstraint1.cty" "hairTip_003_GRP.ty";
connectAttr "hairTip_003_GRP_parentConstraint1.ctz" "hairTip_003_GRP.tz";
connectAttr "hairTip_003_GRP_parentConstraint1.crz" "hairTip_003_GRP.rz";
connectAttr "hairTip_003_GRP_parentConstraint1.cry" "hairTip_003_GRP.ry";
connectAttr "hairTip_003_GRP_parentConstraint1.crx" "hairTip_003_GRP.rx";
connectAttr "hairTip_003_GRP.ro" "hairTip_003_GRP_parentConstraint1.cro";
connectAttr "hairTip_003_GRP.pim" "hairTip_003_GRP_parentConstraint1.cpim";
connectAttr "hairTip_003_GRP.rp" "hairTip_003_GRP_parentConstraint1.crp";
connectAttr "hairTip_003_GRP.rpt" "hairTip_003_GRP_parentConstraint1.crt";
connectAttr "hairTip_002_CTL.t" "hairTip_003_GRP_parentConstraint1.tg[0].tt";
connectAttr "hairTip_002_CTL.rp" "hairTip_003_GRP_parentConstraint1.tg[0].trp";
connectAttr "hairTip_002_CTL.rpt" "hairTip_003_GRP_parentConstraint1.tg[0].trt";
connectAttr "hairTip_002_CTL.r" "hairTip_003_GRP_parentConstraint1.tg[0].tr";
connectAttr "hairTip_002_CTL.ro" "hairTip_003_GRP_parentConstraint1.tg[0].tro";
connectAttr "hairTip_002_CTL.s" "hairTip_003_GRP_parentConstraint1.tg[0].ts";
connectAttr "hairTip_002_CTL.pm" "hairTip_003_GRP_parentConstraint1.tg[0].tpm";
connectAttr "hairTip_003_GRP_parentConstraint1.w0" "hairTip_003_GRP_parentConstraint1.tg[0].tw"
		;
connectAttr "hairTip_000_SKL_parentConstraint1.ctx" "hairTip_000_SKL.tx";
connectAttr "hairTip_000_SKL_parentConstraint1.cty" "hairTip_000_SKL.ty";
connectAttr "hairTip_000_SKL_parentConstraint1.ctz" "hairTip_000_SKL.tz";
connectAttr "hairTip_000_SKL_parentConstraint1.crx" "hairTip_000_SKL.rx";
connectAttr "hairTip_000_SKL_parentConstraint1.cry" "hairTip_000_SKL.ry";
connectAttr "hairTip_000_SKL_parentConstraint1.crz" "hairTip_000_SKL.rz";
connectAttr "hairTip_000_SKL.s" "hairTip_001_SKL.is";
connectAttr "hairTip_001_SKL_parentConstraint1.ctx" "hairTip_001_SKL.tx";
connectAttr "hairTip_001_SKL_parentConstraint1.cty" "hairTip_001_SKL.ty";
connectAttr "hairTip_001_SKL_parentConstraint1.ctz" "hairTip_001_SKL.tz";
connectAttr "hairTip_001_SKL_parentConstraint1.crx" "hairTip_001_SKL.rx";
connectAttr "hairTip_001_SKL_parentConstraint1.cry" "hairTip_001_SKL.ry";
connectAttr "hairTip_001_SKL_parentConstraint1.crz" "hairTip_001_SKL.rz";
connectAttr "hairTip_001_SKL.s" "hairTip_002_SKL.is";
connectAttr "hairTip_002_SKL_parentConstraint1.ctx" "hairTip_002_SKL.tx";
connectAttr "hairTip_002_SKL_parentConstraint1.cty" "hairTip_002_SKL.ty";
connectAttr "hairTip_002_SKL_parentConstraint1.ctz" "hairTip_002_SKL.tz";
connectAttr "hairTip_002_SKL_parentConstraint1.crx" "hairTip_002_SKL.rx";
connectAttr "hairTip_002_SKL_parentConstraint1.cry" "hairTip_002_SKL.ry";
connectAttr "hairTip_002_SKL_parentConstraint1.crz" "hairTip_002_SKL.rz";
connectAttr "hairTip_002_SKL.s" "hairTip_003_SKL.is";
connectAttr "hairTip_003_SKL_parentConstraint1.ctx" "hairTip_003_SKL.tx";
connectAttr "hairTip_003_SKL_parentConstraint1.cty" "hairTip_003_SKL.ty";
connectAttr "hairTip_003_SKL_parentConstraint1.ctz" "hairTip_003_SKL.tz";
connectAttr "hairTip_003_SKL_parentConstraint1.crx" "hairTip_003_SKL.rx";
connectAttr "hairTip_003_SKL_parentConstraint1.cry" "hairTip_003_SKL.ry";
connectAttr "hairTip_003_SKL_parentConstraint1.crz" "hairTip_003_SKL.rz";
connectAttr "hairTip_003_SKL.s" "hairTip_004_SKL.is";
connectAttr "hairTip_004_SKL_parentConstraint1.ctx" "hairTip_004_SKL.tx";
connectAttr "hairTip_004_SKL_parentConstraint1.cty" "hairTip_004_SKL.ty";
connectAttr "hairTip_004_SKL_parentConstraint1.ctz" "hairTip_004_SKL.tz";
connectAttr "hairTip_004_SKL_parentConstraint1.crx" "hairTip_004_SKL.rx";
connectAttr "hairTip_004_SKL_parentConstraint1.cry" "hairTip_004_SKL.ry";
connectAttr "hairTip_004_SKL_parentConstraint1.crz" "hairTip_004_SKL.rz";
connectAttr "hairTip_004_SKL.s" "hairTip_005_SKL.is";
connectAttr "hairTip_004_SKL.ro" "hairTip_004_SKL_parentConstraint1.cro";
connectAttr "hairTip_004_SKL.pim" "hairTip_004_SKL_parentConstraint1.cpim";
connectAttr "hairTip_004_SKL.rp" "hairTip_004_SKL_parentConstraint1.crp";
connectAttr "hairTip_004_SKL.rpt" "hairTip_004_SKL_parentConstraint1.crt";
connectAttr "hairTip_004_SKL.jo" "hairTip_004_SKL_parentConstraint1.cjo";
connectAttr "hairTip_004_CTL.t" "hairTip_004_SKL_parentConstraint1.tg[0].tt";
connectAttr "hairTip_004_CTL.rp" "hairTip_004_SKL_parentConstraint1.tg[0].trp";
connectAttr "hairTip_004_CTL.rpt" "hairTip_004_SKL_parentConstraint1.tg[0].trt";
connectAttr "hairTip_004_CTL.r" "hairTip_004_SKL_parentConstraint1.tg[0].tr";
connectAttr "hairTip_004_CTL.ro" "hairTip_004_SKL_parentConstraint1.tg[0].tro";
connectAttr "hairTip_004_CTL.s" "hairTip_004_SKL_parentConstraint1.tg[0].ts";
connectAttr "hairTip_004_CTL.pm" "hairTip_004_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hairTip_004_SKL_parentConstraint1.w0" "hairTip_004_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hairTip_003_SKL.ro" "hairTip_003_SKL_parentConstraint1.cro";
connectAttr "hairTip_003_SKL.pim" "hairTip_003_SKL_parentConstraint1.cpim";
connectAttr "hairTip_003_SKL.rp" "hairTip_003_SKL_parentConstraint1.crp";
connectAttr "hairTip_003_SKL.rpt" "hairTip_003_SKL_parentConstraint1.crt";
connectAttr "hairTip_003_SKL.jo" "hairTip_003_SKL_parentConstraint1.cjo";
connectAttr "hairTip_003_CTL.t" "hairTip_003_SKL_parentConstraint1.tg[0].tt";
connectAttr "hairTip_003_CTL.rp" "hairTip_003_SKL_parentConstraint1.tg[0].trp";
connectAttr "hairTip_003_CTL.rpt" "hairTip_003_SKL_parentConstraint1.tg[0].trt";
connectAttr "hairTip_003_CTL.r" "hairTip_003_SKL_parentConstraint1.tg[0].tr";
connectAttr "hairTip_003_CTL.ro" "hairTip_003_SKL_parentConstraint1.tg[0].tro";
connectAttr "hairTip_003_CTL.s" "hairTip_003_SKL_parentConstraint1.tg[0].ts";
connectAttr "hairTip_003_CTL.pm" "hairTip_003_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hairTip_003_SKL_parentConstraint1.w0" "hairTip_003_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hairTip_002_SKL.ro" "hairTip_002_SKL_parentConstraint1.cro";
connectAttr "hairTip_002_SKL.pim" "hairTip_002_SKL_parentConstraint1.cpim";
connectAttr "hairTip_002_SKL.rp" "hairTip_002_SKL_parentConstraint1.crp";
connectAttr "hairTip_002_SKL.rpt" "hairTip_002_SKL_parentConstraint1.crt";
connectAttr "hairTip_002_SKL.jo" "hairTip_002_SKL_parentConstraint1.cjo";
connectAttr "hairTip_002_CTL.t" "hairTip_002_SKL_parentConstraint1.tg[0].tt";
connectAttr "hairTip_002_CTL.rp" "hairTip_002_SKL_parentConstraint1.tg[0].trp";
connectAttr "hairTip_002_CTL.rpt" "hairTip_002_SKL_parentConstraint1.tg[0].trt";
connectAttr "hairTip_002_CTL.r" "hairTip_002_SKL_parentConstraint1.tg[0].tr";
connectAttr "hairTip_002_CTL.ro" "hairTip_002_SKL_parentConstraint1.tg[0].tro";
connectAttr "hairTip_002_CTL.s" "hairTip_002_SKL_parentConstraint1.tg[0].ts";
connectAttr "hairTip_002_CTL.pm" "hairTip_002_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hairTip_002_SKL_parentConstraint1.w0" "hairTip_002_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hairTip_001_SKL.ro" "hairTip_001_SKL_parentConstraint1.cro";
connectAttr "hairTip_001_SKL.pim" "hairTip_001_SKL_parentConstraint1.cpim";
connectAttr "hairTip_001_SKL.rp" "hairTip_001_SKL_parentConstraint1.crp";
connectAttr "hairTip_001_SKL.rpt" "hairTip_001_SKL_parentConstraint1.crt";
connectAttr "hairTip_001_SKL.jo" "hairTip_001_SKL_parentConstraint1.cjo";
connectAttr "hairTip_001_CTL.t" "hairTip_001_SKL_parentConstraint1.tg[0].tt";
connectAttr "hairTip_001_CTL.rp" "hairTip_001_SKL_parentConstraint1.tg[0].trp";
connectAttr "hairTip_001_CTL.rpt" "hairTip_001_SKL_parentConstraint1.tg[0].trt";
connectAttr "hairTip_001_CTL.r" "hairTip_001_SKL_parentConstraint1.tg[0].tr";
connectAttr "hairTip_001_CTL.ro" "hairTip_001_SKL_parentConstraint1.tg[0].tro";
connectAttr "hairTip_001_CTL.s" "hairTip_001_SKL_parentConstraint1.tg[0].ts";
connectAttr "hairTip_001_CTL.pm" "hairTip_001_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hairTip_001_SKL_parentConstraint1.w0" "hairTip_001_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "hairTip_000_SKL.ro" "hairTip_000_SKL_parentConstraint1.cro";
connectAttr "hairTip_000_SKL.pim" "hairTip_000_SKL_parentConstraint1.cpim";
connectAttr "hairTip_000_SKL.rp" "hairTip_000_SKL_parentConstraint1.crp";
connectAttr "hairTip_000_SKL.rpt" "hairTip_000_SKL_parentConstraint1.crt";
connectAttr "hairTip_000_SKL.jo" "hairTip_000_SKL_parentConstraint1.cjo";
connectAttr "hairTop_CTL.t" "hairTip_000_SKL_parentConstraint1.tg[0].tt";
connectAttr "hairTop_CTL.rp" "hairTip_000_SKL_parentConstraint1.tg[0].trp";
connectAttr "hairTop_CTL.rpt" "hairTip_000_SKL_parentConstraint1.tg[0].trt";
connectAttr "hairTop_CTL.r" "hairTip_000_SKL_parentConstraint1.tg[0].tr";
connectAttr "hairTop_CTL.ro" "hairTip_000_SKL_parentConstraint1.tg[0].tro";
connectAttr "hairTop_CTL.s" "hairTip_000_SKL_parentConstraint1.tg[0].ts";
connectAttr "hairTop_CTL.pm" "hairTip_000_SKL_parentConstraint1.tg[0].tpm";
connectAttr "hairTip_000_SKL_parentConstraint1.w0" "hairTip_000_SKL_parentConstraint1.tg[0].tw"
		;
connectAttr "pSphere1_translateX.o" "pSphere1.tx";
connectAttr "pSphere1_translateY.o" "pSphere1.ty";
connectAttr "pSphere1_translateZ.o" "pSphere1.tz";
connectAttr "pSphere1_rotateX.o" "pSphere1.rx";
connectAttr "pSphere1_rotateY.o" "pSphere1.ry";
connectAttr "pSphere1_rotateZ.o" "pSphere1.rz";
connectAttr "polySphere1.out" "pSphereShape1.i";
relationship "link" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
connectAttr "layerManager.dli[0]" "defaultLayer.id";
connectAttr "renderLayerManager.rlmi[0]" "defaultRenderLayer.rlid";
connectAttr ":defaultArnoldDenoiser.msg" ":defaultArnoldRenderOptions.imagers" -na
		;
connectAttr ":defaultArnoldDisplayDriver.msg" ":defaultArnoldRenderOptions.drivers"
		 -na;
connectAttr ":defaultArnoldFilter.msg" ":defaultArnoldRenderOptions.filt";
connectAttr ":defaultArnoldDriver.msg" ":defaultArnoldRenderOptions.drvr";
connectAttr "hairTop_CTL.twist" "hair_Twist000_MDN.i1x";
connectAttr "unitConversion1.o" "hair_Twist000_MDN.i1y";
connectAttr "hairBtm_CTL.twist" "hair_Twist000_MDN.i1z";
connectAttr "hairMid_CTL.ry" "unitConversion1.i";
connectAttr "hairTop_CTL.twist" "hair_Twist001_MDN.i1x";
connectAttr "unitConversion2.o" "hair_Twist001_MDN.i1y";
connectAttr "hairBtm_CTL.twist" "hair_Twist001_MDN.i1z";
connectAttr "hairMid_CTL.ry" "unitConversion2.i";
connectAttr "hairTop_CTL.twist" "hair_Twist002_MDN.i1x";
connectAttr "unitConversion3.o" "hair_Twist002_MDN.i1y";
connectAttr "hairBtm_CTL.twist" "hair_Twist002_MDN.i1z";
connectAttr "hairMid_CTL.ry" "unitConversion3.i";
connectAttr "hairTop_CTL.twist" "hair_Twist003_MDN.i1x";
connectAttr "unitConversion4.o" "hair_Twist003_MDN.i1y";
connectAttr "hairBtm_CTL.twist" "hair_Twist003_MDN.i1z";
connectAttr "hairMid_CTL.ry" "unitConversion4.i";
connectAttr "hairTop_CTL.twist" "hair_Twist004_MDN.i1x";
connectAttr "unitConversion5.o" "hair_Twist004_MDN.i1y";
connectAttr "hairBtm_CTL.twist" "hair_Twist004_MDN.i1z";
connectAttr "hairMid_CTL.ry" "unitConversion5.i";
connectAttr "hairTop_CTL.twist" "hair_Twist005_MDN.i1x";
connectAttr "unitConversion6.o" "hair_Twist005_MDN.i1y";
connectAttr "hairBtm_CTL.twist" "hair_Twist005_MDN.i1z";
connectAttr "hairMid_CTL.ry" "unitConversion6.i";
connectAttr "hair_Twist000_MDN.ox" "hair_Twist000_PMA.i1[0]";
connectAttr "hair_Twist000_MDN.oy" "hair_Twist000_PMA.i1[1]";
connectAttr "hair_Twist000_MDN.oz" "hair_Twist000_PMA.i1[2]";
connectAttr "hair_Twist001_MDN.ox" "hair_Twist001_PMA.i1[0]";
connectAttr "hair_Twist001_MDN.oy" "hair_Twist001_PMA.i1[1]";
connectAttr "hair_Twist001_MDN.oz" "hair_Twist001_PMA.i1[2]";
connectAttr "hair_Twist002_MDN.ox" "hair_Twist002_PMA.i1[0]";
connectAttr "hair_Twist002_MDN.oy" "hair_Twist002_PMA.i1[1]";
connectAttr "hair_Twist002_MDN.oz" "hair_Twist002_PMA.i1[2]";
connectAttr "hair_Twist003_MDN.ox" "hair_Twist003_PMA.i1[0]";
connectAttr "hair_Twist003_MDN.oy" "hair_Twist003_PMA.i1[1]";
connectAttr "hair_Twist003_MDN.oz" "hair_Twist003_PMA.i1[2]";
connectAttr "hair_Twist004_MDN.ox" "hair_Twist004_PMA.i1[0]";
connectAttr "hair_Twist004_MDN.oy" "hair_Twist004_PMA.i1[1]";
connectAttr "hair_Twist004_MDN.oz" "hair_Twist004_PMA.i1[2]";
connectAttr "hair_Twist005_MDN.ox" "hair_Twist005_PMA.i1[0]";
connectAttr "hair_Twist005_MDN.oy" "hair_Twist005_PMA.i1[1]";
connectAttr "hair_Twist005_MDN.oz" "hair_Twist005_PMA.i1[2]";
connectAttr "hair_Twist000_PMA.o1" "unitConversion7.i";
connectAttr "hair_Twist001_PMA.o1" "unitConversion8.i";
connectAttr "hair_Twist002_PMA.o1" "unitConversion9.i";
connectAttr "hair_Twist003_PMA.o1" "unitConversion10.i";
connectAttr "hair_Twist004_PMA.o1" "unitConversion11.i";
connectAttr "hair_Twist005_PMA.o1" "unitConversion12.i";
connectAttr "hair_000_CRVShape.ws" "hair_000_CIN.ic";
connectAttr "hair_000_CIN.al" "hair_SquashStretch000_MDN.i1x";
connectAttr "hair_GlobalScale000_MDN.ox" "hair_SquashStretch000_MDN.i2x";
connectAttr "tweak1.og[0]" "hair_Geo000_SKN.ip[0].ig";
connectAttr "hair_000_GEOShapeOrig.l" "hair_Geo000_SKN.orggeom[0]";
connectAttr "bindPose1.msg" "hair_Geo000_SKN.bp";
connectAttr "hair_Geo000_FK.wm" "hair_Geo000_SKN.ma[0]";
connectAttr "hair_Geo002_FK.wm" "hair_Geo000_SKN.ma[1]";
connectAttr "hair_Geo000_FK.liw" "hair_Geo000_SKN.lw[0]";
connectAttr "hair_Geo002_FK.liw" "hair_Geo000_SKN.lw[1]";
connectAttr "hair_Geo000_FK.obcc" "hair_Geo000_SKN.ifcl[0]";
connectAttr "hair_Geo002_FK.obcc" "hair_Geo000_SKN.ifcl[1]";
connectAttr "hair_000_GEOShapeOrig.ws" "tweak1.ip[0].ig";
connectAttr "hair_Geo000_GRP.msg" "bindPose1.m[0]";
connectAttr "hair_Geo000_FK.msg" "bindPose1.m[1]";
connectAttr "hair_Geo002_GRP.msg" "bindPose1.m[2]";
connectAttr "hair_Geo002_FK.msg" "bindPose1.m[3]";
connectAttr "hair_Mid000_FOL.msg" "bindPose1.m[4]";
connectAttr "hair_Geo001_GRP.msg" "bindPose1.m[5]";
connectAttr "hair_Geo001_FK.msg" "bindPose1.m[6]";
connectAttr "bindPose1.w" "bindPose1.p[0]";
connectAttr "bindPose1.m[0]" "bindPose1.p[1]";
connectAttr "bindPose1.w" "bindPose1.p[2]";
connectAttr "bindPose1.m[2]" "bindPose1.p[3]";
connectAttr "bindPose1.w" "bindPose1.p[4]";
connectAttr "hair_Mid000_FOL.msg" "bindPose1.p[5]";
connectAttr "hair_Geo001_GRP.msg" "bindPose1.p[6]";
connectAttr "hair_Geo000_FK.bps" "bindPose1.wm[1]";
connectAttr "hair_Geo002_FK.bps" "bindPose1.wm[3]";
connectAttr "hair_Geo001_FK.bps" "bindPose1.wm[6]";
connectAttr "tweak2.og[0]" "hair_Geo001_SKN.ip[0].ig";
connectAttr "hair_001_GEOShapeOrig.l" "hair_Geo001_SKN.orggeom[0]";
connectAttr "hair_Geo000_FK.wm" "hair_Geo001_SKN.ma[0]";
connectAttr "hair_Geo002_FK.wm" "hair_Geo001_SKN.ma[1]";
connectAttr "hair_Geo001_FK.wm" "hair_Geo001_SKN.ma[2]";
connectAttr "hair_Geo000_FK.liw" "hair_Geo001_SKN.lw[0]";
connectAttr "hair_Geo002_FK.liw" "hair_Geo001_SKN.lw[1]";
connectAttr "hair_Geo001_FK.liw" "hair_Geo001_SKN.lw[2]";
connectAttr "hair_Geo000_FK.obcc" "hair_Geo001_SKN.ifcl[0]";
connectAttr "hair_Geo002_FK.obcc" "hair_Geo001_SKN.ifcl[1]";
connectAttr "hair_Geo001_FK.obcc" "hair_Geo001_SKN.ifcl[2]";
connectAttr "bindPose1.msg" "hair_Geo001_SKN.bp";
connectAttr "hair_001_GEOShapeOrig.ws" "tweak2.ip[0].ig";
connectAttr "tweak3.og[0]" "hair_Crv000_SKN.ip[0].ig";
connectAttr "hair_000_CRVShapeOrig.l" "hair_Crv000_SKN.orggeom[0]";
connectAttr "bindPose2.msg" "hair_Crv000_SKN.bp";
connectAttr "hair_Joint_000_DRV.wm" "hair_Crv000_SKN.ma[0]";
connectAttr "hair_Joint_001_DRV.wm" "hair_Crv000_SKN.ma[1]";
connectAttr "hair_Joint_002_DRV.wm" "hair_Crv000_SKN.ma[2]";
connectAttr "hair_Joint_003_DRV.wm" "hair_Crv000_SKN.ma[3]";
connectAttr "hair_Joint_004_DRV.wm" "hair_Crv000_SKN.ma[4]";
connectAttr "hair_Joint_005_DRV.wm" "hair_Crv000_SKN.ma[5]";
connectAttr "hair_Joint_000_DRV.liw" "hair_Crv000_SKN.lw[0]";
connectAttr "hair_Joint_001_DRV.liw" "hair_Crv000_SKN.lw[1]";
connectAttr "hair_Joint_002_DRV.liw" "hair_Crv000_SKN.lw[2]";
connectAttr "hair_Joint_003_DRV.liw" "hair_Crv000_SKN.lw[3]";
connectAttr "hair_Joint_004_DRV.liw" "hair_Crv000_SKN.lw[4]";
connectAttr "hair_Joint_005_DRV.liw" "hair_Crv000_SKN.lw[5]";
connectAttr "hair_Joint_000_DRV.obcc" "hair_Crv000_SKN.ifcl[0]";
connectAttr "hair_Joint_001_DRV.obcc" "hair_Crv000_SKN.ifcl[1]";
connectAttr "hair_Joint_002_DRV.obcc" "hair_Crv000_SKN.ifcl[2]";
connectAttr "hair_Joint_003_DRV.obcc" "hair_Crv000_SKN.ifcl[3]";
connectAttr "hair_Joint_004_DRV.obcc" "hair_Crv000_SKN.ifcl[4]";
connectAttr "hair_Joint_005_DRV.obcc" "hair_Crv000_SKN.ifcl[5]";
connectAttr "hair_000_CRVShapeOrig.ws" "tweak3.ip[0].ig";
connectAttr "hair_Joint_000_FOL.msg" "bindPose2.m[0]";
connectAttr "hair_Joint_000_DRV.msg" "bindPose2.m[1]";
connectAttr "hair_Joint_001_FOL.msg" "bindPose2.m[2]";
connectAttr "hair_Joint_001_DRV.msg" "bindPose2.m[3]";
connectAttr "hair_Joint_002_FOL.msg" "bindPose2.m[4]";
connectAttr "hair_Joint_002_DRV.msg" "bindPose2.m[5]";
connectAttr "hair_Joint_003_FOL.msg" "bindPose2.m[6]";
connectAttr "hair_Joint_003_DRV.msg" "bindPose2.m[7]";
connectAttr "hair_Joint_004_FOL.msg" "bindPose2.m[8]";
connectAttr "hair_Joint_004_DRV.msg" "bindPose2.m[9]";
connectAttr "hair_Joint_005_FOL.msg" "bindPose2.m[10]";
connectAttr "hair_Joint_005_DRV.msg" "bindPose2.m[11]";
connectAttr "bindPose2.w" "bindPose2.p[0]";
connectAttr "bindPose2.m[0]" "bindPose2.p[1]";
connectAttr "bindPose2.w" "bindPose2.p[2]";
connectAttr "bindPose2.m[2]" "bindPose2.p[3]";
connectAttr "bindPose2.w" "bindPose2.p[4]";
connectAttr "bindPose2.m[4]" "bindPose2.p[5]";
connectAttr "bindPose2.w" "bindPose2.p[6]";
connectAttr "bindPose2.m[6]" "bindPose2.p[7]";
connectAttr "bindPose2.w" "bindPose2.p[8]";
connectAttr "bindPose2.m[8]" "bindPose2.p[9]";
connectAttr "bindPose2.w" "bindPose2.p[10]";
connectAttr "bindPose2.m[10]" "bindPose2.p[11]";
connectAttr "hair_Joint_000_DRV.bps" "bindPose2.wm[1]";
connectAttr "hair_Joint_001_DRV.bps" "bindPose2.wm[3]";
connectAttr "hair_Joint_002_DRV.bps" "bindPose2.wm[5]";
connectAttr "hair_Joint_003_DRV.bps" "bindPose2.wm[7]";
connectAttr "hair_Joint_004_DRV.bps" "bindPose2.wm[9]";
connectAttr "hair_Joint_005_DRV.bps" "bindPose2.wm[11]";
connectAttr "hairTop_CTL.tx" "hair_CTL001_TopSDK_GRP_rotateZ.i";
connectAttr "unitConversion13.o" "hair_CTL001_TopRotateSDK_GRP_rotateZ.i";
connectAttr "hairTop_CTL.rz" "unitConversion13.i";
connectAttr "unitConversion14.o" "hair_CTL001_BtmRotateSDK_GRP_rotateZ.i";
connectAttr "hairBtm_CTL.rz" "unitConversion14.i";
connectAttr "hairBtm_CTL.tx" "hair_CTL001_BtmSDK_GRP_rotateZ.i";
connectAttr "hairCOG_CTL.globalScale" "hair_GlobalScale000_MDN.i2x";
connectAttr "unitConversion15.o" "hairExtraTwist000_ADL.i1";
connectAttr "unitConversion16.o" "hairExtraTwist002_ADL.i1";
connectAttr "hairBtm_CTL.ry" "unitConversion15.i";
connectAttr "hairTop_CTL.ry" "unitConversion16.i";
connectAttr "defaultRenderLayer.msg" ":defaultRenderingList1.r" -na;
connectAttr "hair_000_GEOShape.iog" ":initialShadingGroup.dsm" -na;
connectAttr "hair_001_GEOShape.iog" ":initialShadingGroup.dsm" -na;
connectAttr "pSphereShape1.iog" ":initialShadingGroup.dsm" -na;
connectAttr "ikSplineSolver.msg" ":ikSystem.sol" -na;
// End of exampleRig.ma
