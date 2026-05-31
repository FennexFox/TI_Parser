# Terra Invicta Research Catalog

Generated from `TerraInvicta_Data/StreamingAssets/Templates`.

This file is generated. Rebuild it with:

```powershell
python .\tools\build_research_catalog.py
```

Important interpretation notes:

- `requirements` in the JSON is the canonical source for prerequisite logic.
- `prerequisiteNodes` and `edges` are derived from research-node leaves only and intentionally omit objective, milestone, faction, and nation gates.
- `altPrereq0` is represented as an OR alternative for the first `prereqs` entry.

Node count: `867` total, `149` global techs, `718` projects.
Graph edge count: `1720`.

## Global Techs

| Name | dataName | Kind | Category | Cost | Requirements |
| --- | --- | --- | --- | ---: | --- |
| 전열 추진 | ElectrothermalPropulsion | tech | Energy | 500 | DeepSpacePropulsionConcepts |
| 첨단 전자기학 | AdvancedMagnetics | tech | Energy | 1000 |  |
| 고에너지 레이저 | HighEnergyLasers | tech | Energy | 1000 |  |
| 매스 드라이버 | MassDrivers | tech | Energy | 1000 | AdvancedMagnetics |
| 진공 정전기 법칙 | VacuumElectrostaticPrinciples | tech | Energy | 1000 | AdvancedMagnetics |
| 전자기 추진 | ElectromagneticPropulsion | tech | Energy | 1500 | DeepSpacePropulsionConcepts |
| 자기력 조작 | MagneticForceManipulation | tech | Energy | 2500 | AdvancedMagnetics |
| 정전기 추진 | ElectrostaticPropulsion | tech | Energy | 3000 | DeepSpacePropulsionConcepts + VacuumElectrostaticPrinciples |
| 입자 광선 | ParticleCannon | tech | Energy | 5000 | VacuumElectrostaticPrinciples + HighEnergyLasers |
| 고제 노심 핵분열 시스템 | SolidCoreFissionSystems | tech | Energy | 5000 | NuclearFissioninSpace |
| 반물질 격납 | AntimatterContainment | tech | Energy | 10000 | AdvancedHydrogenContainment + AdvancedAtomicManipulation |
| 용융 노심 핵분열 시스템 | MoltenCoreFissionSystems | tech | Energy | 10000 | SolidCoreFissionSystems + AdvancedCarbonManipulation |
| 정전기 플라즈마 가둠 | ElectrostaticPlasmaConfinement | tech | Energy | 15000 | NuclearFusioninSpace + VacuumElectrostaticPrinciples |
| 기체 노심 핵분열 시스템 | GasCoreFissionSystems | tech | Energy | 20000 | MoltenCoreFissionSystems + AdvancedHeatManagementConcepts |
| 첨단 핵분열 시스템 | AdvancedFissionSystems | tech | Energy | 25000 | GasCoreFissionSystems + Superalloys + Neutronics |
| 아크 레이저 | ArcLasers | tech | Energy | 25000 | InfraredCombatLasers + Supercapacitors |
| 토카막 | Tokamaks | tech | Energy | 25000 | MagneticPlasmaConfinementTechniques + NuclearFusioninSpace + AppliedArtificialIntelligence |
| 자기 플라즈마 가둠 | MagneticPlasmaConfinementTechniques | tech | Energy | 35000 | HighTemperatureSuperconductors + SuperconductingMagnets |
| 청정 에너지 | CleanEnergy | tech | Energy | 50000 | DeuteriumHelium3Fusion + ArrivalInternationalDevelopment |
| 중수소-삼중수소 핵융합 | DeuteriumTritiumFusion | tech | Energy | 50000 | NuclearFusioninSpace + Neutronics |
| 자기 노즐 | MagneticNozzles | tech | Energy | 50000 | MagneticPlasmaConfinementTechniques + DeepSpacePropulsionConcepts |
| Z-핀치 기술 | ZPinchTechniques | tech | Energy | 50000 | MagneticPlasmaConfinementTechniques + NuclearFusioninSpace + Supercapacitors |
| 관성 가둠 핵융합 | InertialPlasmaConfinementTechniques | tech | Energy | 65000 | ArcLasers + NuclearFusioninSpace + AdvancedAtomicManipulation |
| 위상 배열 레이저 | PhasedArrayLasers | tech | Energy | 70000 | ArcLasers + Ultracapacitors |
| 무중성자 핵융합 | AneutronicFusion | tech | Energy | 75000 | DeuteriumHelium3Fusion + AdvancedHydrogenContainment |
| 중수소-중수소 핵융합 | DeuteriumDeuteriumFusion | tech | Energy | 75000 | DeuteriumTritiumFusion + Superalloys |
| 중수소-헬륨-3 핵융합 | DeuteriumHelium3Fusion | tech | Energy | 75000 | DeuteriumDeuteriumFusion + HighTemperatureSuperconductors + CarbonNanotubes |
| 미래 기술: 에너지 | FutureTechEnergy | tech | Energy | 100000 |  |
| 양성자-양성자 핵융합 | ProtonProtonFusion | tech | Energy | 100000 | AneutronicFusion + Ultracapacitors |
| 테라와트 핵융합 반응로 | TerawattFusionReactors | tech | Energy | 100000 | DeuteriumHelium3Fusion + Ultracapacitors + Diamondoids |
| 반물질 대량 생산 | AntimatterMassProduction | tech | Energy | 125000 | AntimatterContainment + OurSpaceFuture + ParticleCannon |
| 증강 현실 | AugmentedReality | tech | InformationScience | 1500 |  |
| 광자 컴퓨팅 | PhotonicComputing | tech | InformationScience | 1500 |  |
| 첨단 인공신경망 | AdvancedNeuralNetworks | tech | InformationScience | 5000 | PhotonicComputing |
| 인공두뇌학 | Cybernetics | tech | InformationScience | 5000 | AugmentedReality + Biotechnology |
| 네트워크 속 프로파간다 | NetworkedPropaganda | tech | InformationScience | 10000 | ArrivalMassCommunications + Cybernetics |
| 자가 수리 소프트웨어 | SelfRepairingSoftware | tech | InformationScience | 10000 | AdvancedNeuralNetworks |
| 양자 컴퓨팅 | QuantumComputing | tech | InformationScience | 15000 | AdvancedAtomicManipulation + AdvancedNeuralNetworks + AdvancedHeatManagementConcepts |
| 양자 암호화 | QuantumEncryption | tech | InformationScience | 20000 | QuantumComputing + SelfRepairingSoftware |
| 적응 인공지능 | AppliedArtificialIntelligence | tech | InformationScience | 25000 | AdvancedNeuralNetworks + QuantumComputing |
| 화이트칼라 자동화 | WhiteCollarAutomation | tech | InformationScience | 40000 | ArrivalInternationalDevelopment + SelfRepairingSoftware + AppliedArtificialIntelligence |
| 관리 알고리즘 | AdministrationAlgorithms | tech | InformationScience | 50000 | WhiteCollarAutomation + QuantumEncryption |
| 미래 기술: 정보 과학 | FutureTechInformationScience | tech | InformationScience | 100000 |  |
| 전초 기지 거주지 | OutpostHabs | tech | LifeScience | 1000 | MissionToSpace |
| 생명공학 | Biotechnology | tech | LifeScience | 1500 |  |
| 우주 농업 | SpaceAgriculture | tech | LifeScience | 2500 | SpaceResearch + Biotechnology |
| 우주 의학 | SpaceMedicine | tech | LifeScience | 2500 | SpaceResearch + Biotechnology |
| 도착 후 심리학 | ArrivalPsychology | tech | LifeScience | 5000 | WeAreNotAlone + SpaceMedicine |
| 궤도 거주지 | OrbitalRingHabs | tech | LifeScience | 5000 | AdAstra |
| 예측 유전학 | PredictiveGenetics | tech | LifeScience | 5000 | Biotechnology + PhotonicComputing |
| 정착 거주지 | SettlementHabs | tech | LifeScience | 5000 | AdAstra |
| 확장된 우주 생존 | ExtendedSpaceSurvival | tech | LifeScience | 10000 | InSituResourceUtilization + SpaceAgriculture + ArrivalPsychology |
| 변환 파지 | TransformPhages | tech | LifeScience | 10000 | PredictiveGenetics + Cybernetics |
| 생명체 설계자 | DesignerLifeforms | tech | LifeScience | 30000 | MolecularAssemblers + TransformPhages + ArrivalLaw |
| 식민 거주지 | ColonyHabs | tech | LifeScience | 35000 | OurSpaceFuture + ExtendedSpaceSurvival + SettlementHabs |
| 정신 및 기계 | MindandMachine | tech | LifeScience | 35000 | AppliedArtificialIntelligence + Cybernetics + ArrivalPsychology |
| 링형 거주지 | OrbitalTorusHabs | tech | LifeScience | 35000 | OurSpaceFuture + ExtendedSpaceSurvival + OrbitalRingHabs |
| 유전자 | Genies | tech | LifeScience | 50000 | TransformPhages + AppliedArtificialIntelligence |
| 기후 변화 완화 | ClimateChangeMitigation | tech | LifeScience | 100000 | DesignerLifeforms + CleanEnergy + AdministrationAlgorithms |
| 미래 기술: 생명 과학 | FutureTechLifeScience | tech | LifeScience | 100000 |  |
| 첨단 탄소 조작 | AdvancedCarbonManipulation | tech | Materials | 1000 |  |
| 첨단 화학 로켓 기술 | AdvancedChemicalRocketry | tech | Materials | 1000 |  |
| 궤도 선박 건조 | OrbitalShipbuilding | tech | Materials | 1000 | MissionToSpace |
| 첨단 초전도체 | AdvancedSuperconductors | tech | Materials | 3500 | AdvancedMagnetics |
| 탄소 나노 튜브 | CarbonNanotubes | tech | Materials | 3500 | AdvancedCarbonManipulation |
| 차세대 항공우주 | NextGenerationAerospace | tech | Materials | 5000 | CarbonNanotubes + AdvancedChemicalRocketry |
| 초합금 | Superalloys | tech | Materials | 5000 | AdvancedAtomicManipulation |
| 첨단 원자 조작 | AdvancedAtomicManipulation | tech | Materials | 10000 | AdvancedCarbonManipulation + PhotonicComputing |
| 슈퍼 커패시터 | Supercapacitors | tech | Materials | 10000 | CarbonNanotubes + AdvancedSuperconductors |
| 초전도 자석 | SuperconductingMagnets | tech | Materials | 10000 | MagneticForceManipulation + AdvancedSuperconductors |
| 다이아몬도이드 | Diamondoids | tech | Materials | 15000 | CarbonNanotubes + MolecularAssemblers |
| 중성자학 | Neutronics | tech | Materials | 15000 | AdvancedAtomicManipulation + AdvancedNeuralNetworks + ParticleCannon |
| 첨단 수소 격납고 | AdvancedHydrogenContainment | tech | Materials | 20000 | SuperconductingMagnets + Superalloys |
| 향상된 함선 건조 기술 | ImprovedShipbuildingTechniques | tech | Materials | 20000 | IndustrializationofSpace + NextGenerationAerospace + Superalloys |
| 핵분열 펄서 추진기 | FissionPulseDrives | tech | Materials | 25000 | SolidCoreFissionSystems + CarbonNanotubes + ElectromagneticPropulsion |
| 분자 조립기 | MolecularAssemblers | tech | Materials | 25000 | QuantumComputing |
| 고온 초전도체 | HighTemperatureSuperconductors | tech | Materials | 40000 | AdvancedSuperconductors + AdvancedAtomicManipulation + AdvancedHeatManagementConcepts |
| 울트라 커패시터 | Ultracapacitors | tech | Materials | 40000 | Supercapacitors + MolecularAssemblers |
| 중형 펄서 추진 | HeavyPulsedPropulsion | tech | Materials | 50000 | AdvancedFissionSystems + FissionPulseDrives + ImprovedShipbuildingTechniques |
| 타이타닉 우주선 | TitanicSpacecraft | tech | Materials | 60000 | FleetLogistics + Diamondoids |
| 미래 기술: 재료 | FutureTechMaterials | tech | Materials | 100000 |  |
| 우주 전쟁의 원칙 | PrinciplesofSpaceWarfare | tech | MilitaryScience | 1000 | OrbitalShipbuilding |
| 지향성 에너지 전투 원칙 | DirectedEnergyWarfareDoctrine | tech | MilitaryScience | 2500 | PrinciplesofSpaceWarfare |
| 운동성 전투 원칙 | KineticsWarfareDoctrine | tech | MilitaryScience | 2500 | PrinciplesofSpaceWarfare |
| 미사일 전투 원칙 | MissileWarfareDoctrine | tech | MilitaryScience | 2500 | PrinciplesofSpaceWarfare |
| 지상 군사 과학 | TerrestrialMilitaryScience | tech | MilitaryScience | 3000 | WeAreNotAlone |
| 적외선 전투 레이저 | InfraredCombatLasers | tech | MilitaryScience | 5000 | HighEnergyLasers + DirectedEnergyWarfareDoctrine |
| 우주 군사화 | MilitarizationofSpace | tech | MilitaryScience | 5000 | PrinciplesofSpaceWarfare |
| 레일건 | Railguns | tech | MilitaryScience | 5000 | KineticsWarfareDoctrine + MassDrivers |
| 외기권 전투기 | OrbitalFighters | tech | MilitaryScience | 7500 | NextGenerationAerospace + PrinciplesofSpaceWarfare |
| 도착 후 보안 | ArrivalSecurity | tech | MilitaryScience | 10000 | TerrestrialMilitaryScience + ArrivalLaw |
| 우주 강습 원칙 | SpaceAssaultDoctrine | tech | MilitaryScience | 10000 | MilitarizationofSpace + TerrestrialMilitaryScience |
| 우주 해군 | SpaceNavies | tech | MilitaryScience | 10000 | MilitarizationofSpace + AdAstra + NuclearFissioninSpace |
| 플라즈마 무기 | PlasmaWeapons | tech | MilitaryScience | 20000 | Railguns + SuperconductingMagnets |
| 네트워크화된 세계 방어 | NetworkedGlobalDefense | tech | MilitaryScience | 25000 | ArrivalSecurity + QuantumEncryption + TransInterfaceWarfare |
| 경계면 간 전쟁 | TransInterfaceWarfare | tech | MilitaryScience | 25000 | TerrestrialMilitaryScience + VisibleCombatLasers + OrbitalFighters |
| 가시광선 전투 레이저 | VisibleCombatLasers | tech | MilitaryScience | 25000 | InfraredCombatLasers + AdvancedHeatManagementConcepts |
| 첨단 미사일 전쟁 원칙 | AdvancedMissileWarfareDoctrine | tech | MilitaryScience | 30000 | MissileWarfareDoctrine + AdvancedChemicalRocketry + AdvancedNeuralNetworks |
| 코일건 | Coilguns | tech | MilitaryScience | 30000 | Railguns + Supercapacitors + SuperconductingMagnets |
| 표적 생물학 전쟁 | TargetedBiologicalWarfare | tech | MilitaryScience | 30000 | NetworkedGlobalDefense + DesignerLifeforms |
| 반물질 무기 | AntimatterWeaponry | tech | MilitaryScience | 35000 | AntimatterContainment + MilitarizationofSpace |
| 자외선 전투 레이저 | UltravioletCombatLasers | tech | MilitaryScience | 60000 | VisibleCombatLasers + MilitarizationofSpace |
| 미래 기술: 군사 과학 | FutureTechMilitaryScience | tech | MilitaryScience | 100000 |  |
| 우리는 혼자가 아니다 | WeAreNotAlone | tech | SocialScience | 500 |  |
| 우주 관광 | SpaceTourism | tech | SocialScience | 1000 | MissionToSpace |
| 도착 후 국내 정치 | ArrivalDomesticPolitics | tech | SocialScience | 2000 | WeAreNotAlone |
| 도착 후 경제 | ArrivalEconomics | tech | SocialScience | 2500 | WeAreNotAlone |
| 도착 후 사회학 | ArrivalSociology | tech | SocialScience | 2500 | WeAreNotAlone |
| 우주 연구 | SpaceResearch | tech | SocialScience | 2500 | MissionToSpace + AugmentedReality |
| 별을 향하여 | AdAstra | tech | SocialScience | 5000 | MissiontotheMoon + OrbitalShipbuilding |
| 도착 후 국제 개발 | ArrivalInternationalDevelopment | tech | SocialScience | 5000 | ArrivalEconomics + ArrivalInternationalRelations |
| 도착 후 국제 관계 | ArrivalInternationalRelations | tech | SocialScience | 5000 | WeAreNotAlone |
| 도착 후 법률 | ArrivalLaw | tech | SocialScience | 5000 | ArrivalDomesticPolitics + MissionToSpace |
| 도착 후 대중 보도 | ArrivalMassCommunications | tech | SocialScience | 5000 | ArrivalSociology + ArrivalPsychology |
| 우주 연구 감독 | DirectedSpaceResearch | tech | SocialScience | 5000 | SpaceResearch + AdAstra + QuantumComputing |
| 독립 운동 | IndependenceMovements | tech | SocialScience | 5000 | ArrivalDomesticPolitics + ArrivalSociology |
| 제국의 몰락 | FallofEmpires | tech | SocialScience | 10000 | IndependenceMovements + ArrivalInternationalRelations |
| 통합의 움직임 | UnityMovements | tech | SocialScience | 10000 | ArrivalInternationalRelations |
| 우주 산업화 | IndustrializationofSpace | tech | SocialScience | 15000 | OrbitalShipbuilding + SpaceMiningandRefining |
| 도착 후 문화 | ArrivalCulture | tech | SocialScience | 20000 | ArrivalMassCommunications + ArrivalDomesticPolitics |
| 우주 상업 | SpaceCommerce | tech | SocialScience | 20000 | IndustrializationofSpace + ArrivalEconomics + ArrivalLaw |
| 거대 국가 | GreatNations | tech | SocialScience | 25000 | UnityMovements + ArrivalDomesticPolitics |
| 우리 우주의 미래 | OurSpaceFuture | tech | SocialScience | 30000 | SpaceNavies + DirectedSpaceResearch + SpaceCommerce |
| 도착 후 통치 | ArrivalGovernance | tech | SocialScience | 35000 | ArrivalCulture + ArrivalSecurity + OurSpaceFuture |
| 통합된 지구-우주 경제 | IntegratedEarthSpaceEconomy | tech | SocialScience | 40000 | ArrivalInternationalDevelopment + OurSpaceFuture + NextGenerationAerospace |
| 함대 물류 | FleetLogistics | tech | SocialScience | 45000 | SpaceNavies + IntegratedEarthSpaceEconomy + ImprovedShipbuildingTechniques |
| 행성간 정치 | InterplanetaryPolities | tech | SocialScience | 50000 | ColonyHabs + OrbitalTorusHabs + ArrivalGovernance |
| 미래 기술: 사회 과학 | FutureTechSocialScience | tech | SocialScience | 100000 |  |
| 점점 빠르게 | Accelerando | tech | SocialScience | 150000 | MindandMachine + IntegratedEarthSpaceEconomy + ArrivalGovernance |
| 우주로의 임무 | MissionToSpace | tech | SpaceScience | 250 |  |
| 스카이워치 | Skywatch | tech | SpaceScience | 250 |  |
| 심우주 추진 개념 | DeepSpacePropulsionConcepts | tech | SpaceScience | 1000 | MissionToSpace |
| 심태양계 스카이워치 | DeepSystemSkywatch | tech | SpaceScience | 1000 | Skywatch |
| 달로의 임무 | MissiontotheMoon | tech | SpaceScience | 1000 | OutpostHabs |
| 첨단 열 관리 개념 | AdvancedHeatManagementConcepts | tech | SpaceScience | 2500 | DeepSpacePropulsionConcepts |
| 화성으로의 임무 | MissiontoMars | tech | SpaceScience | 2500 | OutpostHabs + Skywatch |
| 금성으로의 임무 | MissiontoVenus | tech | SpaceScience | 2500 | MissiontotheMoon + AdvancedHeatManagementConcepts |
| 우주에서의 핵분열 | NuclearFissioninSpace | tech | SpaceScience | 2500 | DeepSpacePropulsionConcepts |
| 우주 채굴 및 정제 | SpaceMiningandRefining | tech | SpaceScience | 2500 | MassDrivers + OutpostHabs |
| 소행성으로의 임무 | MissiontotheAsteroids | tech | SpaceScience | 3500 | MissiontoMars + SpaceMiningandRefining + DeepSpacePropulsionConcepts |
| 고에너지 전자기 추진 | HighEnergyElectromagneticPropulsion | tech | SpaceScience | 5000 | ElectromagneticPropulsion + SuperconductingMagnets |
| 현장 자원 활용 | InSituResourceUtilization | tech | SpaceScience | 5000 | SpaceMiningandRefining |
| 목성으로의 임무 | MissiontoJupiter | tech | SpaceScience | 10000 | MissiontotheAsteroids |
| 수성으로의 임무 | MissiontotheInnerPlanets | tech | SpaceScience | 15000 | MissiontoVenus + MissiontoMars |
| 토성으로의 임무 | MissiontoSaturn | tech | SpaceScience | 25000 | MissiontoJupiter + NuclearFissioninSpace |
| 핵융합 방법론 | NuclearFusioninSpace | tech | SpaceScience | 50000 | AdvancedSuperconductors + NuclearFissioninSpace + AdvancedHeatManagementConcepts |
| 외행성으로의 임무 | MissiontotheOuterPlanets | tech | SpaceScience | 75000 | MissiontoSaturn + DeepSystemSkywatch + ExtendedSpaceSurvival |
| 반물질 추진 | AntimatterPropulsion | tech | SpaceScience | 100000 | AntimatterMassProduction + MagneticNozzles |
| 미래 기술: 우주 과학 | FutureTechSpaceScience | tech | SpaceScience | 100000 |  |

## Faction Projects

| Name | dataName | Kind | Category | Cost | Requirements |
| --- | --- | --- | --- | ---: | --- |
| 태양광 수집기 | Project_SolarCollector | project | Energy | 100 | (Project_PlatformCore OR Project_OutpostCore) |
| 고체 노심 핵분열 반응로 I | Project_SolidCoreFissionReactorI | project | Energy | 250 | SolidCoreFissionSystems |
| 에너지 연구실 | Project_EnergyLab | project | Energy | 300 | (Project_PlatformCore OR Project_OutpostCore) |
| 핵분열 원자로 | Project_FissionPile | project | Energy | 500 | (Project_PlatformCore OR Project_OutpostCore) + NuclearFissioninSpace |
| 용융 노심 핵분열 반응로 I | Project_MoltenCoreFissionReactorI | project | Energy | 500 | MoltenCoreFissionSystems |
| 고체 노심 핵분열 반응로 II | Project_SolidCoreFissionReactorII | project | Energy | 500 | Project_SolidCoreFissionReactorI |
| 고추력 탐사선 | Project_HighThrustProbes | project | Energy | 600 | AdvancedChemicalRocketry |
| 고체 노심 핵분열 반응로 III | Project_SolidCoreFissionReactorIII | project | Energy | 600 | Project_SolidCoreFissionReactorII |
| 고체 노심 핵분열 반응로 IV | Project_SolidCoreFissionReactorIV | project | Energy | 700 | Project_SolidCoreFissionReactorIII |
| 소형 고체 노심 핵분열 반응로 I | Project_SolidCoreFissionReactorVI | project | Energy | 700 | Project_SolidCoreFissionReactorII |
| 태양광 발전 배열 | Project_SolarArray | project | Energy | 750 | (Project_OrbitalCore OR Project_SettlementCore) + Project_SolarCollector |
| 우주 예인선 | Project_SpaceTugs | project | Energy | 750 | AdvancedChemicalRocketry |
| 용융염 노심 핵분열 반응로 I | Project_MoltenSaltFissionReactorI | project | Energy | 800 | Project_MoltenCoreFissionReactorI + Project_SolidCoreFissionReactorIII |
| 고체 노심 핵분열 반응로 V | Project_SolidCoreFissionReactorV | project | Energy | 800 | Project_SolidCoreFissionReactorIV |
| 소형 고체 노심 핵분열 반응로 II | Project_SolidCoreFissionReactorVII | project | Energy | 800 | Project_SolidCoreFissionReactorVI |
| 증기 노심 핵분열 반응로 I | Project_VaporCoreFissionReactorI | project | Energy | 800 | GasCoreFissionSystems + Project_MoltenCoreFissionReactorII |
| 소형 고체 노심 핵분열 반응로 III | Project_SolidCoreFissionReactorVIII | project | Energy | 900 | Project_SolidCoreFissionReactorVII |
| 에어로스파이크 엔진 | Project_Aerospikes | project | Energy | 1000 | NextGenerationAerospace |
| 상업용 로켓 기업 | Project_CommercialRocketCompanies | project | Energy | 1000 | Project_ReusableRockets |
| 핵분열 반응로 배열 | Project_FissionReactorArray | project | Energy | 1000 | (Project_OrbitalCore OR Project_SettlementCore) + Project_FissionPile |
| 기체 노심 핵분열 반응로 I | Project_GasCoreFissionReactorI | project | Energy | 1000 | GasCoreFissionSystems |
| 고출력 핵분열 원자로 | Project_HeavyFissionPile | project | Energy | 1000 | MoltenCoreFissionSystems + Project_FissionPile |
| 용융 노심 핵분열 반응로 II | Project_MoltenCoreFissionReactorII | project | Energy | 1000 | Project_MoltenCoreFissionReactorI + AdvancedCarbonManipulation |
| 재사용 가능 로켓 | Project_ReusableRockets | project | Energy | 1000 | AdvancedChemicalRocketry |
| 스크램제트 | Project_Scramjets | project | Energy | 1000 | NextGenerationAerospace |
| 태양 증기선 | Project_SolarSteamers | project | Energy | 1000 | ElectrothermalPropulsion |
| 소형 고체 노심 핵분열 반응로 IV | Project_SolidCoreFissionReactorIX | project | Energy | 1000 | Project_SolidCoreFissionReactorVIII |
| 소형 고체 노심 핵분열 반응로 V | Project_SolidCoreFissionReactorX | project | Energy | 1200 | Project_SolidCoreFissionReactorIX |
| 증기 노심 핵분열 반응로 II | Project_VaporCoreFissionReactorII | project | Energy | 1200 | Project_VaporCoreFissionReactorI + AdvancedCarbonManipulation |
| 기체 노심 핵분열 반응로 II | Project_GasCoreFissionReactorII | project | Energy | 1250 | Project_GasCoreFissionReactorI |
| 에너지 연구 센터 | Project_EnergyResearchCenter | project | Energy | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + Project_EnergyLab + DirectedSpaceResearch |
| 기체 노심 핵분열 반응로 III | Project_GasCoreFissionReactorIII | project | Energy | 1500 | Project_GasCoreFissionReactorII + CarbonNanotubes |
| 용융염 노심 핵분열 반응로 II | Project_MoltenSaltFissionReactorII | project | Energy | 1500 | Project_MoltenSaltFissionReactorI + Project_MoltenCoreFissionReactorIII |
| 뮤온 스파이커 | Project_MuonSpiker | project | Energy | 1500 | OrbitalShipbuilding + DeuteriumTritiumFusion + AdvancedAtomicManipulation + ParticleCannon |
| 증기 노심 핵분열 반응로 III | Project_VaporCoreFissionReactorIII | project | Energy | 1500 | Superalloys + CarbonNanotubes + Project_VaporCoreFissionReactorII |
| 지향성 에너지 발사 시스템 | Project_DirectedEnergyLaunchSystems | project | Energy | 2000 | NextGenerationAerospace + InfraredCombatLasers |
| 용융 노심 핵분열 반응로 III | Project_MoltenCoreFissionReactorIII | project | Energy | 2000 | Project_MoltenCoreFissionReactorII + CarbonNanotubes |
| 뉴트로늄 스파이커 | Project_NeutroniumSpiker | project | Energy | 2000 | OrbitalShipbuilding + Project_UltracoldNeutronContainment |
| 원자력 화물선 | Project_NuclearFreighters | project | Energy | 2000 | SolidCoreFissionSystems |
| 정전 가둠 핵융합 반응로 I | Project_ElectrostaticConfinementFusionReactorI | project | Energy | 2500 | DeuteriumTritiumFusion + ElectrostaticPlasmaConfinement |
| 핵융합 원자로 | Project_FusionPile | project | Energy | 2500 | (Project_PlatformCore OR Project_OutpostCore) + DeuteriumTritiumFusion |
| 레이저 엔진 | Project_LaserEngine | project | Energy | 2500 | Project_Warships + HighEnergyLasers + Supercapacitors |
| 거울 전지 핵융합 반응로 I | Project_MirrorCellFusionReactorI | project | Energy | 2500 | DeuteriumTritiumFusion + MagneticPlasmaConfinementTechniques |
| 반물질 스파이커 | Project_AntimatterSpiker | project | Energy | 3000 | OrbitalShipbuilding + AntimatterContainment |
| 핵분열 반응로 농장 | Project_FissionReactorFarm | project | Energy | 3000 | (Project_RingCore OR Project_ColonyCore) + Project_FissionReactorArray |
| 고출력 핵분열 반응로 배열 | Project_HeavyFissionReactorArray | project | Energy | 3000 | GasCoreFissionSystems + Project_HeavyFissionPile + Project_FissionReactorArray |
| 태양광 농장 | Project_SolarFarm | project | Energy | 3000 | (Project_RingCore OR Project_ColonyCore) + Project_SolarArray |
| 사이클로트론 | Project_Cyclotron | project | Energy | 5000 | SuperconductingMagnets + Project_ElectronLance |
| 정전 가둠 핵융합 반응로 II | Project_ElectrostaticConfinementFusionReactorII | project | Energy | 5000 | DeuteriumDeuteriumFusion + Project_ElectrostaticConfinementFusionReactorI |
| 핵융합 반응로 배열 | Project_FusionReactorArray | project | Energy | 5000 | (Project_OrbitalCore OR Project_SettlementCore) + Project_FusionPile |
| 핵융합 토카막 I | Project_FusionTokamakI | project | Energy | 5000 | DeuteriumTritiumFusion + Tokamaks |
| 고출력 핵융합 원자로 | Project_HeavyFusionPile | project | Energy | 5000 | AneutronicFusion + Project_FusionPile |
| 거울 전지 핵융합 반응로 II | Project_MirrorCellFusionReactorII | project | Energy | 5000 | DeuteriumDeuteriumFusion + Project_MirrorCellFusionReactorI |
| 고출력 핵분열 반응로 농장 | Project_HeavyFissionReactorFarm | project | Energy | 6500 | AdvancedFissionSystems + Project_FissionReactorFarm + Project_HeavyFissionReactorArray |
| 고성능 레이저 엔진 | Project_AdvancedLaserEngine | project | Energy | 10000 | Ultracapacitors + Project_LaserEngine |
| 에너지 연구원 | Project_EnergyInstitute | project | Energy | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_EnergyResearchCenter + AdministrationAlgorithms |
| 핵융합 화물선 | Project_FusionFreighters | project | Energy | 10000 | (Project_TritonReflexDrive OR Project_TritonTorusDrive) + Project_NuclearFreighters |
| 핵융합 반응로 농장 | Project_FusionReactorFarm | project | Energy | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_FusionReactorArray |
| 핵융합 토카막 II | Project_FusionTokamakII | project | Energy | 10000 | DeuteriumDeuteriumFusion + Project_FusionTokamakI |
| 고출력 핵융합 반응로 배열 | Project_HeavyFusionReactorArray | project | Energy | 10000 | Project_HeavyFusionPile + Project_FusionReactorArray |
| 하이브리드 가둠 핵융합 반응로 I | Project_HybridConfinementFusionReactorI | project | Energy | 10000 | DeuteriumTritiumFusion + MagneticPlasmaConfinementTechniques + ElectrostaticPlasmaConfinement |
| 관성 핵융합 반응로 I | Project_InertialConfinementFusionReactorI | project | Energy | 10000 | DeuteriumTritiumFusion + InertialPlasmaConfinementTechniques |
| 거울 전지 핵융합 반응로 III | Project_MirrorCellFusionReactorIII | project | Energy | 10000 | DeuteriumHelium3Fusion + Project_MirrorCellFusionReactorII |
| 테라와트급 기체 노심 핵분열 반응로 I | Project_GasCoreFissionReactorIV | project | Energy | 10000 | AdvancedFissionSystems + Project_GasCoreFissionReactorII |
| 테라와트급 기체 노심 핵분열 반응로 II | Project_GasCoreFissionReactorV | project | Energy | 10000 | Project_GasCoreFissionReactorIV |
| 테라와트급 기체 노심 핵분열 반응로 III | Project_GasCoreFissionReactorVI | project | Energy | 10000 | Project_GasCoreFissionReactorV |
| Z-핀치 핵융합 반응로 I | Project_ZPinchFusionReactorI | project | Energy | 10000 | DeuteriumTritiumFusion + ZPinchTechniques |
| 정전 가둠 핵융합 반응로 III | Project_ElectrostaticConfinementFusionReactorIII | project | Energy | 15000 | ProtonProtonFusion + Project_ElectrostaticConfinementFusionReactorII + Project_Exotics |
| 핵융합 토카막 III | Project_FusionTokamakIII | project | Energy | 15000 | DeuteriumHelium3Fusion + Project_FusionTokamakII |
| 관성 핵융합 반응로 II | Project_InertialConfinementFusionReactorII | project | Energy | 15000 | DeuteriumDeuteriumFusion + Project_InertialConfinementFusionReactorI |
| 입자 충돌기 | Project_ParticleCollider | project | Energy | 15000 | AntimatterContainment + ParticleCannon + Project_PlatformCore |
| 지하 방사선 분석 | Project_SubsurfaceRadiatonAnalysis | project | Energy | 15000 | InSituResourceUtilization + AppliedArtificialIntelligence |
| 핵융합 토카막 IV | Project_FusionTokamakIV | project | Energy | 20000 | Project_FusionTokamakIII |
| 하이브리드 가둠 핵융합 반응로 II | Project_HybridConfinementFusionReactorII | project | Energy | 20000 | DeuteriumDeuteriumFusion + Project_HybridConfinementFusionReactorI |
| 관성 핵융합 반응로 III | Project_InertialConfinementFusionReactorIII | project | Energy | 20000 | DeuteriumHelium3Fusion + Project_InertialConfinementFusionReactorII |
| Z-핀치 핵융합 반응로 II | Project_ZPinchFusionReactorII | project | Energy | 20000 | DeuteriumDeuteriumFusion + Project_ZPinchFusionReactorI |
| 반물질 플라즈마 노심 반응로 I | Project_AntimatterPlasmaCoreReactorI | project | Energy | 25000 | AntimatterMassProduction + GasCoreFissionSystems |
| 고출력 핵융합 반응로 농장 | Project_HeavyFusionReactorFarm | project | Energy | 25000 | Project_FusionReactorFarm + Project_HeavyFusionReactorArray + TerawattFusionReactors |
| 관성 핵융합 반응로 IV | Project_InertialConfinementFusionReactorIV | project | Energy | 25000 | AneutronicFusion + Project_InertialConfinementFusionReactorIII |
| 원자파괴장치 | Project_Atomsmasher | project | Energy | 30000 | Project_OrbitalCore + Project_ParticleCollider + AntimatterMassProduction |
| 핵융합 토카막 V | Project_FusionTokamakV | project | Energy | 35000 | ProtonProtonFusion + Project_FusionTokamakIV + Project_Exotics |
| 관성 핵융합 반응로 V | Project_InertialConfinementFusionReactorV | project | Energy | 35000 | TerawattFusionReactors + Project_InertialConfinementFusionReactorIV + Project_Exotics |
| 민간 핵융합 반응로 | Project_CivilianFusionReactors | project | Energy | 50000 | DeuteriumTritiumFusion + ArrivalInternationalDevelopment |
| 하이브리드 가둠 핵융합 반응로 III | Project_HybridConfinementFusionReactorIII | project | Energy | 50000 | InertialPlasmaConfinementTechniques + DeuteriumHelium3Fusion + Project_HybridConfinementFusionReactorII |
| 성간 발사 시설 | Project_InterstellarLaunchingLaser | project | Energy | 50000 | (TerawattFusionReactors OR AntimatterPropulsion) + Project_RingCore + PhasedArrayLasers + Project_ExoticHybridSystems + TitanicSpacecraft + faction:EscapeCouncil |
| Z-핀치 핵융합 반응로 III | Project_ZPinchFusionReactorIII | project | Energy | 50000 | DeuteriumHelium3Fusion + Project_ZPinchFusionReactorII |
| Z-핀치 핵융합 반응로 IV | Project_ZPinchFusionReactorIV | project | Energy | 50000 | AneutronicFusion + Project_ZPinchFusionReactorIII |
| 반물질 플라즈마 노심 반응로 II | Project_AntimatterPlasmaCoreReactorII | project | Energy | 75000 | Project_AntimatterPlasmaCoreReactorI + MagneticPlasmaConfinementTechniques |
| 하이브리드 가둠 핵융합 반응로 IV | Project_HybridConfinementFusionReactorIV | project | Energy | 75000 | AneutronicFusion + TerawattFusionReactors + PlasmaWeapons + Project_HybridConfinementFusionReactorIII |
| 유량 안정화 Z-핀치 핵융합 반응로 | Project_FlowStabilizedZPinchFusionReactor | project | Energy | 80000 | TerawattFusionReactors + Project_ZPinchFusionReactorIV + Project_ExoticHybridSystems |
| 관성 핵융합 반응로 VI | Project_InertialConfinementFusionReactorVI | project | Energy | 100000 | ProtonProtonFusion + Project_InertialConfinementFusionReactorV + Project_ExoticHybridSystems |
| 초대형 입자 가속기 | Project_Supercollider | project | Energy | 100000 | Project_RingCore + Project_Atomsmasher + Accelerando |
| 반물질 플라즈마 노심 반응로 III | Project_AntimatterPlasmaCoreReactorIII | project | Energy | 150000 | Project_AntimatterPlasmaCoreReactorII + Diamondoids + Project_Exotics |
| 반물질 광선 노심 반응로 | Project_AntimatterBeamCoreReactor | project | Energy | 500000 | Project_AntimatterPlasmaCoreReactorIII + Project_ExoticHybridSystems |
| 관성 핵융합 반응로 VII | Project_InertialConfinementFusionReactorVII | project | Energy | 500000 | Accelerando + Project_InertialConfinementFusionReactorVI |
| 자동화된 태양광 수집기 | Project_AutomatedSolarCollector | project | InformationScience | 200 | (Project_AutomatedPlatformCore OR Project_AutomatedOutpostCore) + Project_SolarCollector |
| 자동화된 보급창 | Project_AutomatedSupplyDepot | project | InformationScience | 200 | (Project_AutomatedPlatformCore OR Project_AutomatedOutpostCore) + Project_SupplyDepot |
| 정보 과학 연구실 | Project_InformationScienceLab | project | InformationScience | 300 | (Project_PlatformCore OR Project_OutpostCore) |
| 전자 방해 공격(ECM) | Project_ECM1 | project | InformationScience | 500 | Project_Warships |
| 청음초소 | Project_ListeningPost | project | InformationScience | 500 | Project_PlatformCore + ArrivalSecurity |
| 인재 개발 | Project_ResistanceTalentDevelopment | project | InformationScience | 500 | WeAreNotAlone + Project_TheirSignatures + faction:ResistCouncil |
| 표적화 컴퓨터 | Project_TargetingComputer1 | project | InformationScience | 500 | PhotonicComputing + Project_Warships |
| 자동화된 핵분열 원자로 | Project_AutomatedFissionPile | project | InformationScience | 1000 | (Project_AutomatedPlatformCore OR Project_AutomatedOutpostCore) + Project_FissionPile + WhiteCollarAutomation |
| 자동화된 채굴단지 | Project_AutomatedMiningComplex | project | InformationScience | 1000 | Project_AutomatedOutpostCore + Project_OutpostMiningComplex |
| 자동화된 전초기지 코어 | Project_AutomatedOutpostCore | project | InformationScience | 1000 | Project_OutpostCore + AppliedArtificialIntelligence |
| 자동화된 플랫폼 코어 | Project_AutomatedPlatformCore | project | InformationScience | 1000 | Project_PlatformCore + AppliedArtificialIntelligence |
| 글로벌 감청 네트워크 | Project_GlobalListeningNetwork | project | InformationScience | 1000 | PhotonicComputing + Project_TheirOperations |
| 우주 교통 통제 | Project_SpaceTrafficControl | project | InformationScience | 1200 | WhiteCollarAutomation + SpaceCommerce |
| 사이버네틱 임플란트 | Project_CyberneticImplants | project | InformationScience | 1500 | Cybernetics |
| 정보 과학 연구 센터 | Project_InformationScienceResearchCenter | project | InformationScience | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + Project_InformationScienceLab + DirectedSpaceResearch |
| 자원 시장 관리 | Project_ResourceMarketAdministration | project | InformationScience | 2000 | WhiteCollarAutomation + SpaceMiningandRefining |
| 밀수품 스캐너 | Project_ContrabandScanners | project | InformationScience | 2500 | AdvancedNeuralNetworks |
| 보안 작전 | Project_OperationalSecurity | project | InformationScience | 2500 | MilitarizationofSpace + Project_ResistVictory + faction:ResistCouncil |
| 집중 감독 | Project_DirectedFocus | project | InformationScience | 3000 | WhiteCollarAutomation + AdAstra |
| 향상된 ECM 모듈 | Project_ECM2 | project | InformationScience | 3000 | MissileWarfareDoctrine + SelfRepairingSoftware + Project_ECM1 |
| 정찰 배열 | Project_ReconnaissanceArray | project | InformationScience | 3000 | Project_OrbitalCore + Project_ListeningPost + QuantumEncryption |
| 표적화 컴퓨터 II | Project_TargetingComputer2 | project | InformationScience | 3000 | QuantumComputing + Project_TargetingComputer1 |
| 고급 기후 모델링 | Project_AdvancedClimateModeling | project | InformationScience | 5000 | QuantumComputing + Project_TheirComputers |
| 증강 전투 훈련 | Project_AugmentedCombatTraining | project | InformationScience | 5000 | AugmentedReality |
| 증강 학습 | Project_AugmentedLearning | project | InformationScience | 5000 | AugmentedReality |
| 피해 통제 드론 | Project_DamageControlDrones | project | InformationScience | 5000 | AugmentedReality + Project_Warships + Project_TheirRobotics |
| 신경공학 | Project_NeuralEngineering | project | InformationScience | 5000 | AppliedArtificialIntelligence + Project_CyberneticImplants |
| 자율주행 차량 | Project_SelfDrivingVehicles | project | InformationScience | 8000 | AdvancedNeuralNetworks |
| 알고리즘 경제 관리 | Project_AlgorithmicEconomicManagement | project | InformationScience | 10000 | AdministrationAlgorithms + ArrivalEconomics |
| 민간 광자 컴퓨팅 | Project_CivilianPhotonicComputing | project | InformationScience | 10000 | PhotonicComputing + ArrivalEconomics |
| 민간 양자 컴퓨팅 | Project_CivilianQuantumComputing | project | InformationScience | 10000 | QuantumComputing + SpaceCommerce |
| 고성능 ECM 모듈 | Project_ECM3 | project | InformationScience | 10000 | AdvancedMissileWarfareDoctrine + QuantumEncryption + Project_ECM2 |
| 향상된 종말 유도 시스템 | Project_ImprovedTerminalGuidanceSystems | project | InformationScience | 10000 | AdvancedMissileWarfareDoctrine + SelfRepairingSoftware + milestone:AccessAlienShip |
| 정보 과학 연구원 | Project_InformationScienceInstitute | project | InformationScience | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_InformationScienceResearchCenter + QuantumComputing |
| 네트워크 심리전 | Project_NetworkedPsyops | project | InformationScience | 10000 | NetworkedPropaganda + WhiteCollarAutomation + Project_Psyops |
| 정밀 집중 소프트웨어 | Project_PrecisionFocusingSoftware | project | InformationScience | 10000 | InfraredCombatLasers + AppliedArtificialIntelligence + milestone:AccessAlienShip |
| 소셜 미디어 캠페인 | Project_SocialMediaCampaigns | project | InformationScience | 10000 | NetworkedPropaganda |
| 대상 커뮤니티 지원 | Project_TargetedCommunitySupport | project | InformationScience | 10000 | WhiteCollarAutomation |
| 표적화 컴퓨터 III | Project_TargetingComputer3 | project | InformationScience | 10000 | AppliedArtificialIntelligence + Project_TargetingComputer2 |
| 트레이닝 시뮬레이션 임플란트 | Project_TrainingSimulationImplants | project | InformationScience | 10000 | MindandMachine + Project_CovertOperations |
| 초국가적 협조 | Project_TransnationalCoordination | project | InformationScience | 10000 | AdvancedNeuralNetworks |
| 핵심 지점 포격 조준 | Project_VitalPointShellTargeting | project | InformationScience | 10000 | Railguns + AppliedArtificialIntelligence + milestone:AccessAlienShip |
| 아르고스 단지 | Project_ArgusComplex | project | InformationScience | 15000 | Project_RingCore + Project_ReconnaissanceArray + MindandMachine |
| 사이보그화 | Project_Cyborging | project | InformationScience | 15000 | MindandMachine + Project_NeuralEngineering |
| 네트워크 침입 프로토콜 | Project_NetworkIntrusionProtocols | project | InformationScience | 15000 | AppliedArtificialIntelligence + NetworkedGlobalDefense |
| 예측 물류 시스템 | Project_PredictiveLogisticsSystems | project | InformationScience | 20000 | TerrestrialMilitaryScience + WhiteCollarAutomation |
| 알고리즘 추출 관리 | Project_AlgorithmicExtractionManagement | project | InformationScience | 50000 | AdministrationAlgorithms + SpaceCommerce |
| 초국가적 관리 | Project_TransnationalManagement | project | InformationScience | 50000 | AdministrationAlgorithms + Project_TransnationalCoordination |
| 거주지 숙소 | Project_Quarters | project | LifeScience | 200 | (Project_PlatformCore OR Project_OutpostCore) + MissionToSpace |
| 기후 연구실 | Project_ClimateLab | project | LifeScience | 300 | Project_PlatformCore |
| 수경재배실 | Project_HydroponicsBay | project | LifeScience | 300 | (Project_PlatformCore OR Project_OutpostCore) + SpaceAgriculture |
| 생명 과학 연구실 | Project_LifeScienceLab | project | LifeScience | 300 | (Project_PlatformCore OR Project_OutpostCore) |
| 농장 | Project_Farm | project | LifeScience | 1000 | (Project_OrbitalCore OR Project_SettlementCore) + Project_HydroponicsBay |
| 고추력 인체공학 | Project_High-ThrustErgonomics | project | LifeScience | 1000 | Biotechnology + Project_Warships |
| 궤도 거주지 코어 | Project_OrbitalCore | project | LifeScience | 1000 | Project_PlatformCore + OrbitalRingHabs |
| 우주 의료 센터 | Project_OrbitalHospital | project | LifeScience | 1000 | Project_OrbitalCore + SpaceMedicine |
| 주거 모듈 | Project_ResidentialModule | project | LifeScience | 1000 | (Project_OrbitalCore OR Project_SettlementCore) + Project_Quarters + ExtendedSpaceSurvival + SpaceCommerce |
| 정착지 코어 | Project_SettlementCore | project | LifeScience | 1000 | Project_OutpostCore + SettlementHabs |
| 기후 연구 센터 | Project_ClimateResearchCenter | project | LifeScience | 1500 | Project_OrbitalCore + Project_ClimateLab + ArrivalInternationalDevelopment |
| 생명 과학 연구 센터 | Project_LifeScienceResearchCenter | project | LifeScience | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + Project_LifeScienceLab + DirectedSpaceResearch |
| 우주 비행사 피트니스 요법 | Project_AstronautFitnessRegimen | project | LifeScience | 2500 | SpaceMedicine + Project_High-ThrustErgonomics |
| 민간 복합단지 | Project_CivilianComplex | project | LifeScience | 3000 | (Project_RingCore OR Project_ColonyCore) + Project_ResidentialModule + InterplanetaryPolities |
| 식민지 코어 | Project_ColonyCore | project | LifeScience | 3000 | Project_SettlementCore + ColonyHabs |
| 심문 기법 | Project_InterrogationTechniques | project | LifeScience | 3500 | ArrivalPsychology + AugmentedReality |
| 농업 복합단지 | Project_AgricultureComplex | project | LifeScience | 5000 | (Project_RingCore OR Project_ColonyCore) + Project_Farm + DesignerLifeforms |
| 탄소 재포집 기술 | Project_CarbonRecaptureTechnologies | project | LifeScience | 5000 | ClimateChangeMitigation |
| 생태 안정화 프로그램 | Project_EcologicalStabilizationPrograms | project | LifeScience | 5000 | DesignerLifeforms |
| 링형 거주지 코어 | Project_RingCore | project | LifeScience | 5000 | Project_OrbitalCore + OrbitalTorusHabs |
| 우주 병원 | Project_GeriatricsFacility | project | LifeScience | 5000 | Project_RingCore + Project_OrbitalHospital + TransformPhages |
| 가속도 약물학 | Project_AccelerationPharmaceuticals | project | LifeScience | 10000 | ExtendedSpaceSurvival |
| 기후 기관 | Project_ClimateInstitute | project | LifeScience | 10000 | Project_RingCore + Project_ClimateResearchCenter + IntegratedEarthSpaceEconomy |
| 생명 과학 연구원 | Project_LifeScienceInstitute | project | LifeScience | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_LifeScienceResearchCenter + AppliedArtificialIntelligence |
| 온보딩 변형물질 주입 | Project_OnboardingInjections | project | LifeScience | 10000 | TransformPhages + Project_CovertOperations |
| 단독개체 바이러스 | Project_SingletonViruses | project | LifeScience | 10000 | TargetedBiologicalWarfare |
| -고중력 재조합 | Project_High-GRecombinants | project | LifeScience | 20000 | Genies + Project_AccelerationPharmaceuticals |
| 미생물 드릴 | Project_MicrobialDrills | project | LifeScience | 20000 | InSituResourceUtilization + DesignerLifeforms + Project_ThermalMiningTechniques |
| 침입종 차단 | Project_InvasiveSpeciesContainment | project | LifeScience | 30000 | DesignerLifeforms + Project_XenologicalCulls + Project_WarDogNecropsy + milestone:AccessWarDogCorpus + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| DNA 복구 | Project_DNARepairs | project | LifeScience | 50000 | TransformPhages + SelfRepairingSoftware + MolecularAssemblers |
| 므두셀라 요법 | Project_MethuselahTherapies | project | LifeScience | 75000 | Genies + AdministrationAlgorithms + Project_DNARepairs |
| 연료 전지 II | Project_FuelCellII | project | Materials | 250 | SpaceAgriculture |
| 액화 수소 격납고 | Project_LiquidHydrogenContainment | project | Materials | 250 | OrbitalShipbuilding |
| 칼륨 히트 싱크 | Project_PotassiumHeatSink | project | Materials | 250 | AdvancedHeatManagementConcepts |
| 재료 연구실 | Project_MaterialsLab | project | Materials | 300 | (Project_PlatformCore OR Project_OutpostCore) |
| 연료 전지 III | Project_FuelCellIII | project | Materials | 350 | DesignerLifeforms + Project_FuelCellII |
| 반물질 포획기 | Project_AntimatterTrap | project | Materials | 500 | Project_PlatformCore + AntimatterContainment |
| 몰리브덴 파이프 라디에이터 | Project_MolybdenumPipeRadiator | project | Materials | 500 | OrbitalShipbuilding |
| 수리실 | Project_RepairBay | project | Materials | 500 | MilitarizationofSpace |
| 우주 정거장 | Project_SpaceDock | project | Materials | 500 | (Project_PlatformCore OR Project_OutpostCore) + OrbitalShipbuilding |
| 반물질 수확기 | Project_AntimatterHarvester | project | Materials | 1000 | Project_OrbitalCore + Project_AntimatterTrap |
| 장갑 보강재 | Project_ArmorStruts | project | Materials | 1000 | Superalloys + OrbitalShipbuilding |
| 자동 태양 거울 | Project_AutomatedSolarMirror | project | Materials | 1000 | Project_AutomatedPlatformCore + Project_SolarMirror |
| 구성 요소 장갑 | Project_ComponentArmor | project | Materials | 1000 | ImprovedShipbuildingTechniques |
| 복합재 장갑 | Project_CompositeArmor | project | Materials | 1000 | OrbitalShipbuilding + AdvancedCarbonManipulation |
| 건설 모듈 | Project_ConstructionModule | project | Materials | 1000 | (Project_PlatformCore OR Project_OutpostCore) + IndustrializationofSpace |
| 그래핀 배터리 | Project_GrapheneBattery | project | Materials | 1000 | OrbitalShipbuilding + AdvancedCarbonManipulation |
| 하이브리드 공기 흡입식 로켓 | Project_HybridAir-BreathingRockets | project | Materials | 1000 | NextGenerationAerospace + AdvancedHeatManagementConcepts |
| 탕가니카 호수 다리 | Project_LakeTanganyikaBridge | project | Materials | 1000 | ArrivalInternationalDevelopment |
| 나노 공장 | Project_Nanofactory | project | Materials | 1000 | (Project_OrbitalCore OR Project_SettlementCore) + Project_ConstructionModule + IndustrializationofSpace + AdvancedAtomicManipulation |
| 네벨스코이 해협 터널 | Project_NevelskoyStraitTunnel | project | Materials | 1000 | ArrivalInternationalDevelopment |
| 반응 질량 수집기 | Project_RemassScoop | project | Materials | 1000 | ImprovedShipbuildingTechniques |
| 슬러시 수소 저장 탱크 | Project_SlushHydrogenTankage | project | Materials | 1000 | AdvancedHydrogenContainment + Project_LiquidHydrogenContainment |
| 나트륨 히트 싱크 | Project_SodiumHeatSink | project | Materials | 1000 | AdvancedHeatManagementConcepts |
| 잔지바르 해협 다리 | Project_ZanzibarChannelBridge | project | Materials | 1000 | ArrivalInternationalDevelopment |
| 반물질 농장 | Project_AntimatterFarm | project | Materials | 1500 | Project_RingCore + Project_AntimatterHarvester + MagneticPlasmaConfinementTechniques |
| 재료 연구 센터 | Project_MaterialsResearchCenter | project | Materials | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + Project_MaterialsLab + DirectedSpaceResearch |
| 용융염 히트 싱크 | Project_MoltenSaltHeatSink | project | Materials | 1500 | AdvancedHeatManagementConcepts |
| 조선소 | Project_Shipyard | project | Materials | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + Project_SpaceDock + IndustrializationofSpace |
| 나노튜브 필라멘트 라디에이터 | Project_NanotubeFilamentRadiator | project | Materials | 2000 | AdvancedHeatManagementConcepts + CarbonNanotubes |
| 뿔의 다리 | Project_BridgeoftheHorns | project | Materials | 2500 | ArrivalInternationalDevelopment |
| 디푸 고개 개방 | Project_DiphuPass | project | Materials | 2500 | ArrivalInternationalDevelopment |
| 발포 금속 장갑 | Project_FoamedMetalArmor | project | Materials | 2500 | OrbitalShipbuilding + Superalloys |
| 골드 러시 | Project_GoldRush | project | Materials | 2500 | Project_SettlementMiningComplex + Project_EscapeVictory + faction:EscapeCouncil |
| 리튬 히트 싱크 | Project_LithiumHeatSink | project | Materials | 2500 | AdvancedHeatManagementConcepts + Project_MolecularBenefication |
| 말라카 해협 다리 | Project_MalaccaStraitBridge | project | Materials | 2500 | ArrivalInternationalDevelopment |
| 팔크 해협 다리 | Project_PalkStraitBridge | project | Materials | 2500 | ArrivalInternationalDevelopment |
| 양자 배터리 | Project_QuantumBattery | project | Materials | 2500 | OrbitalShipbuilding + AdvancedAtomicManipulation |
| 태양 거울 | Project_SolarMirror | project | Materials | 2500 | Project_PlatformCore + Project_SolarCollector + AdvancedHeatManagementConcepts |
| 티란 해협 가도 | Project_StraitofTiranCauseway | project | Materials | 2500 | ArrivalInternationalDevelopment |
| 순다 해협 다리 | Project_SundaStraitBridge | project | Materials | 2500 | ArrivalInternationalDevelopment |
| 와칸 회랑 프로젝트 | Project_WakhanCorridorProject | project | Materials | 2500 | ArrivalInternationalDevelopment |
| 이온 분진 라디에이터 | Project_IonicDustRadiator | project | Materials | 3000 | AdvancedHeatManagementConcepts + VacuumElectrostaticPrinciples |
| 코발트 분진 라디에이터 | Project_CobaltDustRadiator | project | Materials | 5000 | AdvancedHeatManagementConcepts + MagneticForceManipulation |
| 다리엔 갭 도로 | Project_DarienGapRoad | project | Materials | 5000 | ArrivalInternationalDevelopment |
| 엑조틱 히트 싱크 | Project_ExoticHeatSink | project | Materials | 5000 | AdvancedHeatManagementConcepts + Project_Exotics |
| 수소 양이온 포집기 | Project_HydronTrap | project | Materials | 5000 | AdvancedAtomicManipulation + Project_SlushHydrogenTankage + Project_ExoticHybridSystems |
| 나노튜브 장갑 | Project_NanotubeArmor | project | Materials | 5000 | OrbitalShipbuilding + CarbonNanotubes |
| 인양실 | Project_SalvageBay | project | Materials | 5000 | IndustrializationofSpace + AdvancedAtomicManipulation |
| 태양 거울 배열 | Project_SolarMirrorArray | project | Materials | 5000 | Project_OrbitalCore + Project_SolarMirror + Superalloys + AppliedArtificialIntelligence |
| 스페이스웍스 | Project_Spaceworks | project | Materials | 5000 | (Project_RingCore OR Project_ColonyCore) + Project_Shipyard + SpaceNavies |
| 지브롤터 해협 횡단 | Project_StraitofGibraltarCrossing | project | Materials | 5000 | ArrivalInternationalDevelopment + Superalloys |
| 초전도 코일 배터리 | Project_SuperconductingCoilBattery | project | Materials | 5000 | ImprovedShipbuildingTechniques + HighTemperatureSuperconductors |
| 탈싱키 터널 | Project_TalsinkiTunnel | project | Materials | 5000 | ArrivalInternationalDevelopment |
| 열 채굴 기술 | Project_ThermalMiningTechniques | project | Materials | 5000 | SpaceMiningandRefining + AdvancedHeatManagementConcepts |
| 북쪽 해협 횡단 | Project_NorthChannelCrossing | project | Materials | 7500 | ArrivalInternationalDevelopment + Superalloys |
| 소야 해협 다리 | Project_SoyaStraitBridge | project | Materials | 7500 | ArrivalInternationalDevelopment |
| 아다만틴 장갑 | Project_AdamantaneArmor | project | Materials | 10000 | ImprovedShipbuildingTechniques + Diamondoids |
| 배터리 농장 | Project_BatteryFarms | project | Materials | 10000 | (Project_QuantumBattery OR Project_SuperconductingCoilBattery) + ArrivalInternationalDevelopment |
| 베링 해협 횡단 | Project_BeringStraitCrossing | project | Materials | 10000 | ArrivalInternationalDevelopment + Superalloys |
| 엑조틱 장갑 | Project_ExoticArmor | project | Materials | 10000 | ImprovedShipbuildingTechniques + Project_Exotics |
| 엑조틱 스파이크 라디에이터 | Project_ExoticSpikeRadiator | project | Materials | 10000 | AdvancedHeatManagementConcepts + Project_ExoticHybridSystems |
| 하이브리드 장갑 | Project_HybridArmor | project | Materials | 10000 | Project_ExoticArmor + Project_AdamantaneArmor |
| 산업용 원자 조립기 | Project_IndustrialAtomicAssemblers | project | Materials | 10000 | MolecularAssemblers + ArrivalInternationalDevelopment + Project_TheirRobotics |
| 재료 연구원 | Project_MaterialsInstitute | project | Materials | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_MaterialsResearchCenter + AppliedArtificialIntelligence |
| 군대 핵 방어 강화 | Project_NuclearHardening | project | Materials | 10000 | NetworkedGlobalDefense + Project_ExoticArmor |
| 신속한 군사 프로토타입 제작 | Project_RapidMilitaryPrototyping | project | Materials | 10000 | TerrestrialMilitaryScience + MolecularAssemblers + Project_TheirTechnology |
| 신속한 수리 재료 | Project_RapidRepairingMaterials | project | Materials | 10000 | (TerrestrialMilitaryScience OR ImprovedShipbuildingTechniques) + MolecularAssemblers |
| 주석 방울 라디에이터 | Project_TinDropletRadiator | project | Materials | 10000 | AdvancedHeatManagementConcepts + SuperconductingMagnets |
| 초저온 중성자 격납고 | Project_UltracoldNeutronContainment | project | Materials | 10000 | Neutronics + Diamondoids + Project_Exotics |
| 도시 방어 강화 | Project_UrbanArmoring | project | Materials | 10000 | NetworkedGlobalDefense + Project_MegafaunaNecropsy + milestone:AccessAlienMegafauna |
| 심우주 금속 공학 | Project_DeepSpaceMetallurgy | project | Materials | 15000 | SpaceMiningandRefining + AppliedArtificialIntelligence |
| 자기부상 열차 | Project_MaglevTrains | project | Materials | 15000 | SuperconductingMagnets |
| 나노 제조 복합단지 | Project_NanofacturingComplex | project | Materials | 15000 | (Project_RingCore OR Project_ColonyCore) + Project_Nanofactory + MolecularAssemblers |
| 급속 증류 기술 | Project_RapidDistillationTechniques | project | Materials | 15000 | SpaceMiningandRefining + TransformPhages |
| 광재 활용 | Project_SlagValorization | project | Materials | 15000 | SpaceCommerce + Superalloys |
| 정수 기술 | Project_WaterPurificationTechniques | project | Materials | 15000 | SpaceMiningandRefining + AdvancedAtomicManipulation |
| 갈륨 안개 라디에이터 | Project_GalliumMistRadiator | project | Materials | 20000 | AdvancedHeatManagementConcepts + SuperconductingMagnets + ImprovedShipbuildingTechniques + Project_MolecularBenefication |
| 분자 선광처리 | Project_MolecularBenefication | project | Materials | 20000 | SpaceMiningandRefining + MolecularAssemblers |
| 플라즈마 추출 기술 | Project_PlasmaExtractionTechniques | project | Materials | 20000 | SpaceCommerce + ElectrostaticPlasmaConfinement |
| 급속 핵분열 물질 농축 | Project_RapidFissileEnrichment | project | Materials | 20000 | SpaceMiningandRefining + MolecularAssemblers + AppliedArtificialIntelligence |
| 솔레타 | Project_Soletta | project | Materials | 20000 | Project_RingCore + Project_SolarMirrorArray + Diamondoids + AdministrationAlgorithms + Ultracapacitors |
| 리튬 스프레이 라디에이터 | Project_LithiumSprayRadiator | project | Materials | 30000 | AdvancedHeatManagementConcepts + SuperconductingMagnets + ImprovedShipbuildingTechniques + Project_MolecularBenefication |
| 먼지 플라즈마 라디에이터 | Project_DustyPlasmaRadiator | project | Materials | 40000 | AdvancedHeatManagementConcepts + MagneticPlasmaConfinementTechniques + ImprovedShipbuildingTechniques + OurSpaceFuture |
| 행성간 전투함 | Project_Warships | project | MilitaryScience | 250 | OrbitalShipbuilding |
| 거점 방어 레이저 포탑 | Project_PointDefenseLaserTurret | project | MilitaryScience | 250 | DirectedEnergyWarfareDoctrine |
| 해병 소대 병영 | Project_MarinePlatoonBarracks | project | MilitaryScience | 300 | (Project_PlatformCore OR Project_OutpostCore) + MilitarizationofSpace |
| 군사 과학 연구실 | Project_MilitaryScienceLab | project | MilitaryScience | 300 | (Project_PlatformCore OR Project_OutpostCore) |
| 거점 방어 배열 | Project_PointDefenseArray | project | MilitaryScience | 300 | (Project_PlatformCore OR Project_OutpostCore) + InfraredCombatLasers |
| 40mm 기관포 | Project_40mmAutocannon | project | MilitaryScience | 500 | KineticsWarfareDoctrine + Project_Warships |
| 인재 개발 | Project_HumanityFirstTalentDevelopment | project | MilitaryScience | 500 | WeAreNotAlone + Project_TheirSignatures + faction:DestroyCouncil |
| 적외선 레이저 포대 | Project_60cmIRLaserBattery | project | MilitaryScience | 500 | InfraredCombatLasers |
| 킬러의 본능 | Project_KillerInstinct | project | MilitaryScience | 500 | Project_HumanityFirstTalentDevelopment + faction:DestroyCouncil |
| 적외선 레이저 대포 | Project_240cmIRLaserCannon | project | MilitaryScience | 500 | InfraredCombatLasers |
| 탄약고 | Project_Magazine | project | MilitaryScience | 500 | Project_Warships |
| 해병 돌격 부대 | Project_MarineAssaultUnit | project | MilitaryScience | 500 | MilitarizationofSpace |
| 하이드로록스 폭발형 탄두 미사일 | Project_CopperheadMissileBay | project | MilitaryScience | 650 | MissileWarfareDoctrine + Project_CryogenicLiquid-FuelRockets |
| 전자 광선 포대 | Project_EBeamBatteries | project | MilitaryScience | 800 | ParticleCannon + DirectedEnergyWarfareDoctrine |
| 접촉점화성 파편형 탄두 미사일 | Project_RattlerMissileBay | project | MilitaryScience | 800 | MissileWarfareDoctrine + Project_Liquid-FuelRockets |
| 접촉점화성 폭발형 탄두 미사일 | Project_AnacondaMissileBay | project | MilitaryScience | 800 | MissileWarfareDoctrine + Project_Liquid-FuelRockets |
| 고급 해병 돌격 부대 | Project_AdvancedMarineAssaultUnit | project | MilitaryScience | 1000 | SpaceAssaultDoctrine + Project_MarineAssaultUnit |
| 전자 랜스 | Project_ElectronLance | project | MilitaryScience | 1000 | ParticleCannon + DirectedEnergyWarfareDoctrine + Project_PatrolVessels |
| 하이드로록스 파편형 탄두 미사일 | Project_ViperMissileBay | project | MilitaryScience | 1000 | MissileWarfareDoctrine + Project_CryogenicLiquid-FuelRockets |
| 적층 방어 배열 | Project_LayeredDefenseArray | project | MilitaryScience | 1000 | (Project_OrbitalCore OR Project_SettlementCore) + Project_PointDefenseArray + MilitarizationofSpace |
| 해병 중대 병영 | Project_MarineCompanyBarracks | project | MilitaryScience | 1000 | (Project_OrbitalCore OR Project_SettlementCore) + SpaceAssaultDoctrine + Project_MarinePlatoonBarracks |
| 거점 방어 아크 레이저 포탑 | Project_PointDefenseArcLaserTurret | project | MilitaryScience | 1000 | ArcLasers |
| 하이드로록스 관통형 탄두 미사일 | Project_LanceheadMissileBay | project | MilitaryScience | 1500 | AdvancedMissileWarfareDoctrine + Project_CryogenicLiquid-FuelRockets |
| 접촉점화성 관통형 탄두 미사일 | Project_HarlequinMissileBay | project | MilitaryScience | 1500 | AdvancedMissileWarfareDoctrine + Project_Liquid-FuelRockets |
| 적외선 아크 레이저 포대 | Project_60cmIRArcLaserBattery | project | MilitaryScience | 1500 | ArcLasers |
| 적외선 아크 레이저 대포 | Project_240cmIRArcLaserCannon | project | MilitaryScience | 1500 | ArcLasers |
| 군사 과학 연구 센터 | Project_MilitaryScienceResearchCenter | project | MilitaryScience | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + Project_MilitaryScienceLab + DirectedSpaceResearch |
| 거점 방어 페이저 포탑 | Project_PointDefensePhaserTurret | project | MilitaryScience | 1500 | PhasedArrayLasers |
| 하이드로록스 연료형 핵 미사일 | Project_HadesNuclearTorpedoBay | project | MilitaryScience | 2000 | AdvancedMissileWarfareDoctrine + MilitarizationofSpace + Project_CryogenicLiquid-FuelRockets |
| 접촉점화성 연료 핵 어뢰 | Project_CerebrusNuclearTorpedoBay | project | MilitaryScience | 2000 | AdvancedMissileWarfareDoctrine + Project_Liquid-FuelRockets |
| 핵추진 파편화 탄두 어뢰 | Project_ZeusTorpedoBay | project | MilitaryScience | 2000 | AdvancedMissileWarfareDoctrine + Project_SolidCoreFissionReactorVI |
| 핵추진 폭발형 탄두 어뢰 | Project_AthenaTorpedoBay | project | MilitaryScience | 2000 | AdvancedMissileWarfareDoctrine + Project_SolidCoreFissionReactorVI |
| 초계 함선 | Project_PatrolVessels | project | MilitaryScience | 2000 | Project_Warships + PrinciplesofSpaceWarfare |
| 최고의 인재 | Project_BestandBrightest | project | MilitaryScience | 2500 | Project_Warships + Project_CooperateVictory + faction:CooperateCouncil |
| 정예 해병 돌격 부대 | Project_EliteMarineAssaultUnit | project | MilitaryScience | 2500 | OurSpaceFuture + Project_AdvancedMarineAssaultUnit |
| 적외선 페이저 포대 | Project_60cmIRPhaserBattery | project | MilitaryScience | 2500 | PhasedArrayLasers |
| 적외선 페이저 대포 | Project_240cmIRPhaserCannon | project | MilitaryScience | 2500 | PhasedArrayLasers |
| 이온 포대 | Project_IonBatteries | project | MilitaryScience | 2500 | AdvancedAtomicManipulation + Project_EBeamBatteries |
| 이온 대포 | Project_IonCannon | project | MilitaryScience | 2500 | AdvancedAtomicManipulation + Project_ElectronLance |
| 우주군 기본 훈련 | Project_SpaceForceBasicTraining | project | MilitaryScience | 2500 | MilitarizationofSpace |
| 우주항 보안 프레임워크 | Project_SpaceportSecurityFramework | project | MilitaryScience | 2500 | ArrivalSecurity |
| 레일 대포 | Project_RailCannonMk1 | project | MilitaryScience | 3000 | Railguns |
| 레일건 포대 | Project_RailgunBatteryMk1 | project | MilitaryScience | 3000 | Railguns |
| 향상된 레일 대포 | Project_RailCannonMk2 | project | MilitaryScience | 4000 | Project_RailCannonMk1 + MagneticForceManipulation |
| 향상된 레일건 포대 | Project_RailgunBatteryMk2 | project | MilitaryScience | 4000 | Project_RailgunBatteryMk1 + MagneticForceManipulation |
| 고성능 레일 대포 | Project_RailCannonMk3 | project | MilitaryScience | 5000 | Project_RailCannonMk2 |
| 고성능 레일건 포대 | Project_RailgunBatteryMk3 | project | MilitaryScience | 5000 | Project_RailgunBatteryMk2 |
| 군대 분산 전술 | Project_ArmyDispersionTactics | project | MilitaryScience | 5000 | TransInterfaceWarfare |
| 전투 기지 | Project_Battlestations | project | MilitaryScience | 5000 | (Project_RingCore OR Project_ColonyCore) + Project_LayeredDefenseArray + VisibleCombatLasers |
| 간부 양성 프로그램 | Project_CadreDevelopmentPrograms | project | MilitaryScience | 5000 | TerrestrialMilitaryScience + WhiteCollarAutomation + Project_AugmentedCombatTraining |
| 코일 대포 | Project_CoilCannonMk1 | project | MilitaryScience | 5000 | Coilguns |
| 코일건 포대 | Project_CoilgunBatteryMk1 | project | MilitaryScience | 5000 | Coilguns |
| 대외계인 팀 | Project_CounteralienOperationsTeams | project | MilitaryScience | 5000 | Project_RapidResponseTeams + Project_CadreDevelopmentPrograms + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil |
| 반란 진압 작전 | Project_CounterinsurgencyOperations | project | MilitaryScience | 5000 | TerrestrialMilitaryScience + ArrivalInternationalDevelopment |
| 기함 함교 | Project_FlagBridge | project | MilitaryScience | 5000 | SpaceNavies + Project_PatrolVessels |
| 녹색 레이저 포대 | Project_60cmGreenLaserBattery | project | MilitaryScience | 5000 | VisibleCombatLasers |
| 녹색 레이저 대포 | Project_240cmGreenLaserCannon | project | MilitaryScience | 5000 | VisibleCombatLasers |
| 유격전 | Project_GuerrillaWarfare | project | MilitaryScience | 5000 | TerrestrialMilitaryScience + ArrivalDomesticPolitics |
| 극초음속 해상발사 순항미사일 | Project_HypersonicSea-LaunchedCruiseMissiles | project | MilitaryScience | 5000 | NextGenerationAerospace |
| 해병 대대 병영 | Project_MarineBattalionBarracks | project | MilitaryScience | 5000 | (Project_RingCore OR Project_ColonyCore) + Project_MarineCompanyBarracks |
| 산악전 원칙 | Project_MountainWarfareDoctrine | project | MilitaryScience | 5000 | TerrestrialMilitaryScience |
| 네메시스 핵어뢰 | Project_NemesisNuclearTorpedoBay | project | MilitaryScience | 5000 | AdvancedMissileWarfareDoctrine + MilitarizationofSpace + Project_SolidCoreFissionReactorVII |
| 핵추진 관통형 탄두 어뢰 | Project_AresTorpedoBay | project | MilitaryScience | 5000 | AdvancedMissileWarfareDoctrine + Project_SolidCoreFissionReactorVI |
| 입자 광선 포대 | Project_ParticleBeamBatteries | project | MilitaryScience | 5000 | Supercapacitors + Project_IonBatteries |
| 입자 랜스 | Project_ParticleLance | project | MilitaryScience | 5000 | Supercapacitors + Project_IonCannon |
| 플라즈마 포대 | Project_PlasmaBatteryMk1 | project | MilitaryScience | 5000 | PlasmaWeapons + Project_PatrolVessels |
| 플라즈마 대포 | Project_PlasmaCannonMk1 | project | MilitaryScience | 5000 | PlasmaWeapons + Project_FleetCombatants |
| 심리전 | Project_Psyops | project | MilitaryScience | 5000 | ArrivalDomesticPolitics + ArrivalPsychology + TerrestrialMilitaryScience |
| 우주 해군 사관학교 | Project_SpaceNavyAcademies | project | MilitaryScience | 5000 | SpaceNavies |
| 전술 드론 | Project_TacticalDrones | project | MilitaryScience | 5000 | TerrestrialMilitaryScience + SelfRepairingSoftware + Project_TheirRobotics |
| 시가전 원칙 | Project_UrbanWarfareDoctrine | project | MilitaryScience | 5000 | TerrestrialMilitaryScience + AdvancedNeuralNetworks |
| 해군 현대화 | Project_WetNavyModernization | project | MilitaryScience | 5000 | TerrestrialMilitaryScience + MolecularAssemblers + AdvancedMissileWarfareDoctrine |
| 함대 전투함 | Project_FleetCombatants | project | MilitaryScience | 6000 | Project_PatrolVessels + MilitarizationofSpace |
| 자유의 전사 | Project_FreedomFighters | project | MilitaryScience | 7500 | IndependenceMovements + Project_GuerrillaWarfare |
| 녹색 아크 레이저 포대 | Project_60cmGreenArcLaserBattery | project | MilitaryScience | 7500 | VisibleCombatLasers + ArcLasers |
| 녹색 아크 레이저 대포 | Project_240cmGreenArcLaserCannon | project | MilitaryScience | 7500 | VisibleCombatLasers + ArcLasers |
| 향상된 플라즈마 포대 | Project_PlasmaBatteryMk2 | project | MilitaryScience | 7500 | (MagneticPlasmaConfinementTechniques OR ElectrostaticPlasmaConfinement) + Ultracapacitors + Project_PlasmaBatteryMk1 |
| 향상된 플라즈마 대포 | Project_PlasmaCannonMk2 | project | MilitaryScience | 7500 | (MagneticPlasmaConfinementTechniques OR ElectrostaticPlasmaConfinement) + Ultracapacitors + Project_PlasmaCannonMk1 |
| 자외선 레이저 포대 | Project_60cmUVLaserBattery | project | MilitaryScience | 7500 | UltravioletCombatLasers |
| 자외선 레이저 대포 | Project_240cmUVLaserCannon | project | MilitaryScience | 7500 | UltravioletCombatLasers |
| 함대 장교 교육 기관 | Project_FleetOfficerSchoolhouses | project | MilitaryScience | 10000 | FleetLogistics |
| 모든 영역에서의 제병연합 | Project_FullSpectrumCombinedArms | project | MilitaryScience | 10000 | TransInterfaceWarfare + Project_Warships |
| 이모탈 | Project_Immortals | project | MilitaryScience | 10000 | Project_EliteMarineAssaultUnit + Project_SubmitVictory + Project_LoyaltyTraining + faction:SubmitCouncil |
| 향상된 코일 대포 | Project_CoilCannonMk2 | project | MilitaryScience | 10000 | Project_CoilCannonMk1 + HighTemperatureSuperconductors + Superalloys |
| 향상된 코일건 포대 | Project_CoilgunBatteryMk2 | project | MilitaryScience | 10000 | Project_CoilgunBatteryMk1 + HighTemperatureSuperconductors + Superalloys |
| 군사 과학 연구원 | Project_MilitaryScienceInstitute | project | MilitaryScience | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_MilitaryScienceResearchCenter + AppliedArtificialIntelligence + ArrivalSecurity |
| 성형작약 핵 미사일 | Project_OlympusNuclearTorpedoBay | project | MilitaryScience | 10000 | AdvancedMissileWarfareDoctrine + FissionPulseDrives + MilitarizationofSpace + Project_SolidCoreFissionReactorVIII |
| 고성능 플라즈마 포대 | Project_PlasmaBatteryMk3 | project | MilitaryScience | 10000 | Project_PlasmaBatteryMk2 + Coilguns + Project_Exotics |
| 고성능 플라즈마 대포 | Project_PlasmaCannonMk3 | project | MilitaryScience | 10000 | Project_PlasmaCannonMk2 + Coilguns + Project_Exotics |
| 레지스탕스 레인저 | Project_Rangers | project | MilitaryScience | 10000 | Project_EliteMarineAssaultUnit + Project_ResistVictory + Project_GuerrillaWarfare + faction:ResistCouncil |
| 신속한 안정화 작전 | Project_RapidStabilizationOperations | project | MilitaryScience | 10000 | NetworkedGlobalDefense + Project_CounterinsurgencyOperations + Project_Psyops |
| 전열함 | Project_ShipsoftheLine | project | MilitaryScience | 10000 | Project_FleetCombatants + ImprovedShipbuildingTechniques |
| 휴머니티 퍼스트 스파르탄 | Project_Spartans | project | MilitaryScience | 10000 | Project_EliteMarineAssaultUnit + Project_DestroyVictory + Project_CadreDevelopmentPrograms + faction:DestroyCouncil |
| 지역 방위 대대 | Project_TerritorialDefenseBattalions | project | MilitaryScience | 10000 | NetworkedGlobalDefense |
| 타이탄 | Project_Titans | project | MilitaryScience | 10000 | Project_ShipsoftheLine + TitanicSpacecraft |
| 자외선 아크 레이저 포대 | Project_60cmUVArcLaserBattery | project | MilitaryScience | 10000 | UltravioletCombatLasers + ArcLasers |
| 자외선 아크 레이저 대포 | Project_240cmUVArcLaserCannon | project | MilitaryScience | 10000 | UltravioletCombatLasers + ArcLasers |
| 녹색 페이저 포대 | Project_60cmGreenPhaserBattery | project | MilitaryScience | 12000 | VisibleCombatLasers + PhasedArrayLasers + Project_Exotics |
| 녹색 페이저 대포 | Project_240cmGreenPhaserCannon | project | MilitaryScience | 12000 | VisibleCombatLasers + PhasedArrayLasers + Project_Exotics |
| 아케론 성형작약 핵어뢰 | Project_AcheronNuclearTorpedoBay | project | MilitaryScience | 15000 | HeavyPulsedPropulsion + Project_OlympusNuclearTorpedoBay |
| 고성능 코일 대포 | Project_CoilCannonMk3 | project | MilitaryScience | 15000 | Project_CoilCannonMk2 + Ultracapacitors + Project_Exotics |
| 고성능 코일건 포대 | Project_CoilgunBatteryMk3 | project | MilitaryScience | 15000 | Project_CoilgunBatteryMk2 + Ultracapacitors + Project_Exotics |
| 반물질 입자 대포 | Project_AntimatterParticleCannon | project | MilitaryScience | 15000 | AntimatterWeaponry + Project_ParticleLance |
| 자외선 페이저 포대 | Project_60cmUVPhaserBattery | project | MilitaryScience | 18000 | UltravioletCombatLasers + PhasedArrayLasers + Project_ExoticHybridSystems |
| 자외선 페이저 대포 | Project_240cmUVPhaserCannon | project | MilitaryScience | 18000 | UltravioletCombatLasers + PhasedArrayLasers + Project_ExoticHybridSystems |
| 반물질 어뢰 | Project_AntimatterTorpedoLauncher | project | MilitaryScience | 20000 | AdvancedMissileWarfareDoctrine + AntimatterWeaponry + Project_SolidCoreFissionReactorIX |
| 센티넬 복합단지 | Project_SentinelComplex | project | MilitaryScience | 20000 | Project_RingCore + Project_Exotics + NetworkedGlobalDefense + ArrivalCulture + faction:AppeaseCouncil |
| 지능형 우주선 방어 시스템 | Project_SmartSpacecraftDefenses | project | MilitaryScience | 20000 | AppliedArtificialIntelligence + Project_TheirTechnology + Project_Warships |
| 타르타로스 성형작약 핵어뢰 | Project_TartarusNuclearTorpedoBay | project | MilitaryScience | 25000 | Diamondoids + Project_AcheronNuclearTorpedoBay + Project_Exotics |
| 독립 지휘부 | Project_IndependentCommands | project | MilitaryScience | 50000 | FleetLogistics |
| 중앙 고정형 중성자 랜스 | Project_SpinalNeutronLance | project | MilitaryScience | 50000 | AdvancedFissionSystems + Project_UltracoldNeutronContainment + Project_ParticleLance + Project_ShipsoftheLine + Project_ExoticHybridSystems |
| 스틱스 성형작약 핵어뢰 | Project_StyxNuclearTorpedoBay | project | MilitaryScience | 50000 | Project_ExoticHybridSystems + Project_TartarusNuclearTorpedoBay |
| 대중 연구 | Project_AudienceResearch | project | SocialScience | 100 |  |
| 상업 연구 | Project_CommercialResearch | project | SocialScience | 100 |  |
| 작전 연구 | Project_OperationsResearch | project | SocialScience | 100 |  |
| 관광객 침실 | Project_TouristBerth | project | SocialScience | 200 | Project_PlatformCore + SpaceTourism |
| 유럽의 탈식민화 | Project_EuropeanDecolonization | project | SocialScience | 250 | IndependenceMovements |
| 사회 과학 연구실 | Project_SocialScienceLab | project | SocialScience | 300 | (Project_PlatformCore OR Project_OutpostCore) |
| 인재 개발 | Project_AcademyTalentDevelopment | project | SocialScience | 500 | WeAreNotAlone + Project_TheirSignatures + faction:CooperateCouncil |
| 방송국 | Project_BroadcastOutlet | project | SocialScience | 500 | (Project_PlatformCore OR Project_OutpostCore) + ArrivalMassCommunications |
| 자본화 | Project_Capitalization | project | SocialScience | 500 | ArrivalEconomics + faction:ExploitCouncil |
| 카리브 공동체 | Project_CaribbeanCommunity | project | SocialScience | 500 | ArrivalInternationalRelations + nation:JAM |
| 다 좋자고 하는 일 | Project_ForTheGreaterGood | project | SocialScience | 500 | ArrivalSociology + faction:AppeaseCouncil |
| 높은 데 있는 친구들 | Project_FriendsinHighPlaces | project | SocialScience | 500 | ArrivalDomesticPolitics + faction:ResistCouncil |
| 인재 개발 | Project_InitiativeTalentDevelopment | project | SocialScience | 500 | WeAreNotAlone + Project_TheirSignatures + faction:ExploitCouncil |
| 한민족 | Project_OnePeople | project | SocialScience | 500 | ArrivalMassCommunications + Project_ServantTalentDevelopment + faction:SubmitCouncil |
| 인재 개발 | Project_ProtectorateTalentDevelopment | project | SocialScience | 500 | WeAreNotAlone + Project_TheirSignatures + faction:AppeaseCouncil |
| 외계인의 위협 공표 | Project_PublicizeAlienThreat | project | SocialScience | 500 | WeAreNotAlone + Project_TheirOperations + faction:ResistCouncil/DestroyCouncil/EscapeCouncil |
| 인재 개발 | Project_ServantTalentDevelopment | project | SocialScience | 500 | WeAreNotAlone + Project_TheirSignatures + faction:SubmitCouncil |
| 전략적 로비 활동 | Project_StrategicLobbying | project | SocialScience | 500 | ArrivalDomesticPolitics |
| 상아탑 | Project_TheIvoryTower | project | SocialScience | 500 | ArrivalSociology + ArrivalDomesticPolitics + faction:CooperateCouncil |
| 비밀 조직 | Project_ClandestineCells | project | SocialScience | 600 | WeAreNotAlone |
| 통일의 시대 | Project_APeriodofUnity | project | SocialScience | 1000 | UnityMovements + nation:VNM |
| 관리 노드 | Project_AdministrationNode | project | SocialScience | 1000 | (Project_PlatformCore OR Project_OutpostCore) + AdvancedNeuralNetworks + ArrivalDomesticPolitics |
| 아프리카 독립 운동 | Project_AfricanIndependenceMovements | project | SocialScience | 1000 | IndependenceMovements |
| 미국 해방 운동 | Project_AmericanLiberationMovements | project | SocialScience | 1000 | IndependenceMovements |
| 시장 진출 | Project_ArrivalStockMarkets | project | SocialScience | 1000 | ArrivalEconomics |
| 아시아 태평양 지역주의 운동 | Project_Asia-PacificRegionalistMovements | project | SocialScience | 1000 | IndependenceMovements |
| 켈트 리그 | Project_CelticLeague | project | SocialScience | 1000 | UnityMovements + nation:IRL |
| 중앙 아메리카 연합국 | Project_CentralAmericanConfederation | project | SocialScience | 1000 | UnityMovements + nation:GTM |
| 중앙 아시아 연합 | Project_CentralAsianUnion | project | SocialScience | 1000 | UnityMovements + nation:KAZ |
| 중앙 통신 시설 | Project_CommunicationsHub | project | SocialScience | 1000 | (Project_OrbitalCore OR Project_SettlementCore) + Project_BroadcastOutlet + NetworkedPropaganda |
| 회랑 외교 | Project_CorridorDiplomacy | project | SocialScience | 1000 | ArrivalInternationalRelations |
| 유럽 자치 운동 | Project_EuropeanAutonomyMovements | project | SocialScience | 1000 | IndependenceMovements |
| 헝가리 수복운동 | Project_HungarianIrredentism | project | SocialScience | 1000 | UnityMovements + nation:HUN |
| 기관 협력 | Project_InstitutionalOutreach | project | SocialScience | 1000 | ArrivalDomesticPolitics |
| 국가 연구 감독 | Project_NationalResearchOversight | project | SocialScience | 1000 | ArrivalDomesticPolitics |
| 북유럽 연방 | Project_NordicFederation | project | SocialScience | 1000 | UnityMovements + nation:SCA |
| 규제 포획 | Project_RegulatoryCapture | project | SocialScience | 1000 | ArrivalLaw |
| 우주 호텔 | Project_SpaceHotel | project | SocialScience | 1000 | Project_OrbitalCore + Project_TouristBerth |
| 자립형 우주비행 프로그램 | Project_BootstrapSpaceflightPrograms | project | SocialScience | 1200 | AdvancedChemicalRocketry + ArrivalEconomics |
| 기밀 작전 | Project_CovertOperations | project | SocialScience | 1200 | QuantumEncryption + Project_ClandestineCells |
| 관리 연구 | Project_ManagementResearch | project | SocialScience | 1500 |  |
| 스컹크웍스 | Project_SkunkWorks | project | SocialScience | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + AdvancedNeuralNetworks |
| 사회과학 연구 센터 | Project_SocialScienceResearchCenter | project | SocialScience | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + Project_SocialScienceLab + DirectedSpaceResearch |
| 초국가적 투자 | Project_TransnationalInvestments | project | SocialScience | 1500 | ArrivalInternationalDevelopment |
| 관리 타워 | Project_AdministrationTower | project | SocialScience | 2000 | (Project_OrbitalCore OR Project_SettlementCore) + Project_AdministrationNode + WhiteCollarAutomation + ArrivalInternationalRelations |
| 아프리카 연방 | Project_EastAfricanFederation | project | SocialScience | 2000 | ArrivalInternationalRelations + nation:TZA |
| 상업용 광업 회사 | Project_CommercialMiningCompanies | project | SocialScience | 2000 | SpaceCommerce |
| 공동의 대의 | Project_CommonCause | project | SocialScience | 2000 | ArrivalInternationalRelations + ArrivalLaw + objective:ResearchTheirMethods |
| 최대의 노력 | Project_MaximumEffort | project | SocialScience | 2000 | ArrivalLaw + ArrivalEconomics |
| 회사 엔지니어 | Project_CompanyEngineers | project | SocialScience | 2500 | DirectedSpaceResearch + Project_ExploitVictory + faction:ExploitCouncil |
| 참호 | Project_Entrenchment | project | SocialScience | 2500 | ArrivalLaw + Project_AppeaseVictory + faction:AppeaseCouncil |
| 국제 지휘 구조 | Project_GlobalCommandStructure | project | SocialScience | 2500 | IndependenceMovements |
| 소프트 파워의 도구 | Project_InstrumentsofSoftPower | project | SocialScience | 2500 | ArrivalDomesticPolitics + ArrivalCulture |
| 관제소 | Project_OperationsCenter | project | SocialScience | 2500 | (Project_OrbitalCore OR Project_SettlementCore) + AugmentedReality |
| 금지 명령 | Project_Proscription | project | SocialScience | 2500 | ArrivalSecurity + Project_DestroyVictory + faction:DestroyCouncil |
| 지역 아프리카 연합 | Project_RegionalAfricanUnions | project | SocialScience | 2500 | UnityMovements + Project_EastAfricanFederation |
| 복원된 바르샤바 조약 | Project_RestoredWarsawPact | project | SocialScience | 2500 | ArrivalInternationalRelations + nation:RUS |
| 프로젝트 검토 | Project_ReviewFailedProjects | project | SocialScience | 2500 | SpaceResearch |
| 적응형 FDI 모델 | Project_AdapativeFDIModeling | project | SocialScience | 3000 | WhiteCollarAutomation + Project_TransnationalInvestments |
| 관료층 | Project_Apparatchiks | project | SocialScience | 3000 | ArrivalDomesticPolitics + WhiteCollarAutomation |
| 러시아의 해체 | Project_DissolutionofRussia | project | SocialScience | 3000 | FallofEmpires |
| 충성심 훈련 | Project_LoyaltyTraining | project | SocialScience | 3000 | ArrivalCulture + NetworkedPropaganda |
| 우주 리조트 | Project_SpaceResort | project | SocialScience | 3000 | Project_RingCore + Project_SpaceHotel |
| 위기 외교 | Project_UnitedEffort | project | SocialScience | 3000 | ArrivalInternationalRelations + QuantumEncryption + objective:ResearchTheirOperations |
| 관리 복합단지 | Project_AdministrationComplex | project | SocialScience | 5000 | (Project_RingCore OR Project_ColonyCore) + Project_AdministrationTower + AdministrationAlgorithms + ArrivalGovernance |
| 공포에 호소하는 메시지 | Project_AppealtoFearMessaging | project | SocialScience | 5000 | ArrivalPsychology + ArrivalSecurity + ArrivalMassCommunications + Project_TheirOperations + faction:DestroyCouncil/ExploitCouncil/SubmitCouncil/AppeaseCouncil |
| 희망에 호소하는 메시지 | Project_AppealtoHopeMessaging | project | SocialScience | 5000 | ArrivalCulture + Project_TheirOperations + faction:ResistCouncil/EscapeCouncil/CooperateCouncil |
| 자율 연구 그룹 | Project_AutonomousResearchGroups | project | SocialScience | 5000 | DirectedSpaceResearch + SelfRepairingSoftware |
| 집중 훈련 프로그램 | Project_CrashTrainingProgram | project | SocialScience | 5000 | AugmentedReality + Project_CovertOperations |
| 아메리카 제국의 종말 | Project_EndofAmerica | project | SocialScience | 5000 | FallofEmpires |
| 인도의 종말 | Project_EndofIndia | project | SocialScience | 5000 | FallofEmpires |
| 외부화된 비용 | Project_ExternalizedCosts | project | SocialScience | 5000 | ArrivalEconomics + faction:ExploitCouncil/AppeaseCouncil/EscapeCouncil |
| 자유주 연합 | Project_FreistaatConfederation | project | SocialScience | 5000 | UnityMovements + nation:DEU |
| 걸프 협력 위원회 | Project_GulfCooperationCouncil | project | SocialScience | 5000 | UnityMovements + nation:SAU |
| 유도된 변곡점 | Project_InducedInflectionPoints | project | SocialScience | 5000 | Accelerando |
| 기관 요새화 | Project_InstitutionalBastions | project | SocialScience | 5000 | ArrivalLaw + ArrivalInternationalDevelopment |
| 통합된 자원 시장 | Project_IntegratedResourceMarket | project | SocialScience | 5000 | IntegratedEarthSpaceEconomy |
| 미디어 센터 | Project_MediaCenter | project | SocialScience | 5000 | (Project_RingCore OR Project_ColonyCore) + Project_CommunicationsHub + ArrivalCulture |
| 미디어 리터러시 교육 | Project_MediaLiteracyTraining | project | SocialScience | 5000 | ArrivalCulture |
| 나이지리아 연합국 | Project_NigerianConfederation | project | SocialScience | 5000 | UnityMovements + Project_RegionalAfricanUnions + nation:NGA |
| 남미의 관리인 | Project_GranColombia | project | SocialScience | 5000 | UnityMovements |
| 동남아시아 동맹 | Project_SoutheastAsianAlliance | project | SocialScience | 5000 | GreatNations + nation:THA |
| 남십자성 공화국 | Project_SouthernCross | project | SocialScience | 5000 | UnityMovements + nation:AUS |
| 이해관계자 전복 | Project_StakeholderSubversion | project | SocialScience | 5000 | ArrivalEconomics + AdvancedNeuralNetworks |
| 총력전 프레임 | Project_TotalWarFraming | project | SocialScience | 5000 | NetworkedPropaganda + faction:SubmitCouncil/DestroyCouncil/ExploitCouncil |
| 말레이 연합 국가 | Project_UnitedMalayNation | project | SocialScience | 5000 | UnityMovements + nation:MYS |
| 중국의 종말 | Project_EndofChina | project | SocialScience | 6000 | FallofEmpires |
| 고위직 특권 | Project_ExecutivePrivilege | project | SocialScience | 7500 | ArrivalLaw |
| 정부 네트워크 분석 | Project_GovernmentNetworkAnalysis | project | SocialScience | 7500 | ArrivalDomesticPolitics + AppliedArtificialIntelligence |
| 승인된 수사 | Project_SanctionedInvestigations | project | SocialScience | 7500 | ArrivalLaw |
| 공통 관심사 | Project_ACommonConcern | project | SocialScience | 10000 | ArrivalCulture + ArrivalEconomics + Project_TheirOperations + faction:ResistCouncil/CooperateCouncil/EscapeCouncil/SubmitCouncil |
| 민방위 프로그램 | Project_CivilDefensePrograms | project | SocialScience | 10000 | ArrivalSecurity |
| 지휘 센터 | Project_CommandCenter | project | SocialScience | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_OperationsCenter + QuantumEncryption + FleetLogistics |
| 복원된 연방국 | Project_CommonwealthRestored | project | SocialScience | 10000 | (Project_EndofAmerica OR Project_ForwardRussia) + UnityMovements + nation:GBR |
| 암호화된 연구 시스템 | Project_EncryptedResearchSystems | project | SocialScience | 10000 | QuantumEncryption |
| 주조소 | Project_Foundry | project | SocialScience | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_SkunkWorks + AdministrationAlgorithms |
| 위대한 자치령 | Project_GreaterDominion | project | SocialScience | 10000 | GreatNations + Project_EndofAmerica + nation:CSA |
| 대 인도네시아 | Project_GreaterIndonesia | project | SocialScience | 10000 | UnityMovements + nation:IDN |
| 대 말레이시아 | Project_GreaterMalaysia | project | SocialScience | 10000 | GreatNations + Project_UnitedMalayNation + nation:MYS |
| 국립 연구실 | Project_NationalLabs | project | SocialScience | 10000 | ArrivalLaw + Project_NationalResearchOversight |
| 인테르마리움 | Project_SlavicCommonwealth | project | SocialScience | 10000 | UnityMovements + nation:POL |
| 사회 과학 연구원 | Project_SocialScienceInstitute | project | SocialScience | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_SocialScienceResearchCenter + AdministrationAlgorithms |
| 남미 연합 | Project_SouthAmericanUnion | project | SocialScience | 10000 | GreatNations + Project_GranColombia + nation:BOL |
| 남부의 관리인 | Project_StewardoftheSouth | project | SocialScience | 10000 | GreatNations + Project_GranColombia + nation:BRA |
| 시아국 | Project_TheShiaNation | project | SocialScience | 10000 | UnityMovements + nation:IRN |
| 아칸드 바라트 | Project_GreaterIndia | project | SocialScience | 15000 | GreatNations + nation:IND |
| 태평양 방위 연맹 | Project_PacificLeague | project | SocialScience | 15000 | (Project_Pan-AsianCooperative OR Project_EndofAmerica) + nation:JPN |
| 통합 콜롬비아 | Project_UnidadColombia | project | SocialScience | 15000 | GreatNations + Project_GranColombia + nation:COL |
| 연합된 투르키스탄 | Project_UnitedTurkestan | project | SocialScience | 15000 | UnityMovements + nation:TUR |
| 아프리카 연합 | Project_AfricanUnion | project | SocialScience | 20000 | GreatNations + Project_RegionalAfricanUnions + nation:ETH |
| 대아프리카 연합 | Project_GreatAfricanUnion | project | SocialScience | 20000 | Project_AfricanUnion |
| 아랍 연맹 | Project_UnitedArabLeague | project | SocialScience | 20000 | UnityMovements + nation:EGY |
| 통합된 북미 | Project_UnitedNorthAmerica | project | SocialScience | 20000 | GreatNations + nation:USA |
| 유럽의 부상 | Project_EuropeAscendant | project | SocialScience | 25000 | UnityMovements + nation:EUA |
| 국가 집중 연구 | Project_FocusedNationalResearch | project | SocialScience | 25000 | ArrivalGovernance + Project_NationalLabs |
| 국제적 야망 | Project_GlobalAmbition | project | SocialScience | 25000 | ArrivalGovernance |
| 위대한 오스트로네시아 | Project_GreaterAustronesia | project | SocialScience | 30000 | GreatNations + Project_GreaterIndonesia + nation:IDN |
| 대인테르마리움 | Project_GreaterIntermarium | project | SocialScience | 30000 | GreatNations + Project_SlavicCommonwealth + Project_DissolutionofRussia |
| 대통합 북미 | Project_GreaterUnitedNorthAmerica | project | SocialScience | 30000 | Project_UnitedNorthAmerica + nation:USA |
| 글로벌 군비 통제 체제 | Project_GlobalArmsControlRegime | project | SocialScience | 35000 | ArrivalGovernance + faction:CooperateCouncil/AppeaseCouncil |
| 글로벌 대량 살상무기 확산 방지 체제 | Project_GlobalCounterproliferationRegime | project | SocialScience | 35000 | ArrivalGovernance + faction:CooperateCouncil/AppeaseCouncil |
| 칼리프국 | Project_TheCaliphate | project | SocialScience | 35000 | UnityMovements |
| 러시아의 전진 | Project_ForwardRussia | project | SocialScience | 40000 | GreatNations + Project_RestoredWarsawPact + nation:RUS |
| 강대한 범아시아 | Project_GreaterPanAsia | project | SocialScience | 40000 | Project_Pan-AsianCooperative |
| 중국 본토의 해방 | Project_LiberatingMainlandChina | project | SocialScience | 40000 | UnityMovements + nation:TWN |
| 범아시아 연합체 | Project_Pan-AsianCooperative | project | SocialScience | 40000 | GreatNations + nation:CHN |
| 글로벌 제국 | Project_GlobalEmpire | project | SocialScience | 50000 | Accelerando |
| 위대한 유럽 | Project_GreatEuropa | project | SocialScience | 50000 | GreatNations + Project_EuropeAscendant + nation:EUA |
| 독립적인 거주지 | Project_IndependentHabitats | project | SocialScience | 50000 | InterplanetaryPolities |
| 위대한 칼리프국 | Project_TheGreaterCaliphate | project | SocialScience | 50000 | GreatNations + Project_TheCaliphate + nation:CPH |
| 이슬람의 집 | Project_TheHouseofIslam | project | SocialScience | 50000 | GreatNations + Project_TheGreaterCaliphate + nation:CPH |
| 인도 문화권 | Project_UnitedIndosphere | project | SocialScience | 50000 | Project_GreaterIndia |
| 보호국 총독부 | Project_ProtectorateAuthority | project | SocialScience | 500000 | Accelerando + GreatNations + Project_CoexistencePact + faction:AppeaseCouncil |
| 극저온 연료 우주 로켓 | Project_CryogenicLiquid-FuelRockets | project | SpaceScience | 100 | Project_Liquid-FuelRockets |
| 액체 연료 우주 로켓 | Project_Liquid-FuelRockets | project | SpaceScience | 100 | Project_Solid-FuelSpaceRockets |
| 플랫폼 코어 | Project_PlatformCore | project | SpaceScience | 100 |  |
| 고체 연료 우주 로켓 | Project_Solid-FuelSpaceRockets | project | SpaceScience | 100 |  |
| 우주 과학 연구실 | Project_SpaceScienceLab | project | SpaceScience | 100 | (Project_PlatformCore OR Project_OutpostCore) |
| 앰플리트론 추진기 | Project_AmplitronDrive | project | SpaceScience | 200 | ElectrothermalPropulsion |
| E-광선 추진기 | Project_E-BeamDrive | project | SpaceScience | 200 | ElectrothermalPropulsion + HighEnergyLasers |
| 매스 드라이버 | Project_MassDriver | project | SpaceScience | 200 | ElectromagneticPropulsion |
| 플라즈마파 추진기 | Project_PlasmaWaveDrive | project | SpaceScience | 200 | ElectromagneticPropulsion + AdvancedSuperconductors |
| 텅스텐 전기 저항 제트 추진기 | Project_TungstenResistojet | project | SpaceScience | 200 | ElectrothermalPropulsion |
| 키위 추진기 | Project_KiwiDrive | project | SpaceScience | 250 | Project_SolidCoreFissionReactorVI |
| 이동식 우주 과학 연구실 | Project_MobileSpaceScienceLab | project | SpaceScience | 250 | OrbitalShipbuilding + SpaceResearch + MissiontoMars |
| 석영 추진기 | Project_QuartzDrive | project | SpaceScience | 250 | Project_GasCoreFissionReactorI |
| 콜로이드 추진기 | Project_ColloidDrive | project | SpaceScience | 300 | ElectrostaticPropulsion |
| 이온 추진기 | Project_IonDrive | project | SpaceScience | 300 | ElectrostaticPropulsion |
| 네르바 추진기 | Project_NervaDrive | project | SpaceScience | 300 | Project_SolidCoreFissionReactorI |
| 전초기지 코어 | Project_OutpostCore | project | SpaceScience | 300 | OutpostHabs |
| 보급창 | Project_SupplyDepot | project | SpaceScience | 300 | (Project_PlatformCore OR Project_OutpostCore) + OrbitalShipbuilding |
| 태양광 전초기지 키트 | Project_SolarOutpostKit | project | SpaceScience | 350 | Project_OutpostCore + Project_SolarCollector + Project_ConstructionModule |
| 태양광 플랫폼 키트 | Project_SolarPlatformKit | project | SpaceScience | 350 | Project_PlatformCore + Project_SolarCollector + Project_ConstructionModule |
| VASIMR | Project_VASIMR | project | SpaceScience | 400 | ElectromagneticPropulsion |
| 핵분열 전초기지 키트 | Project_FissionOutpostKit | project | SpaceScience | 500 | Project_OutpostCore + Project_FissionPile + Project_ConstructionModule |
| 핵분열 플랫폼 키트 | Project_FissionPlatformKit | project | SpaceScience | 500 | Project_PlatformCore + Project_FissionPile + Project_ConstructionModule |
| 행성간 화학 로켓 | Project_ImprovedInterplanetaryRockets | project | SpaceScience | 500 | AdvancedChemicalRocketry + Project_CryogenicLiquid-FuelRockets |
| 전초기지 채굴단지 | Project_OutpostMiningComplex | project | SpaceScience | 500 | Project_OutpostCore + SpaceMiningandRefining |
| 인재 개발 | Project_ProjectExodusTalentDevelopment | project | SpaceScience | 500 | WeAreNotAlone + Project_TheirSignatures + faction:EscapeCouncil |
| 펄스 플라스모이드 추진기 | Project_PulsedPlasmoidDrive | project | SpaceScience | 500 | ElectromagneticPropulsion + Supercapacitors |
| 로켓 과학자 | Project_RocketScientists | project | SpaceScience | 500 | AdvancedChemicalRocketry + faction:EscapeCouncil |
| 스네어 추진기 | Project_SnareDrive | project | SpaceScience | 500 | Project_SolidCoreFissionReactorVII |
| 초전도 매스 드라이버 | Project_SuperconductingMassDriver | project | SpaceScience | 500 | HighEnergyElectromagneticPropulsion + Project_MassDriver + SuperconductingMagnets |
| 초중량 화학 로켓 | Project_SuperheavyRockets | project | SpaceScience | 500 | AdvancedChemicalRocketry |
| 공동 추진기 | Project_CavityDrive | project | SpaceScience | 750 | Project_VaporCoreFissionReactorI |
| 세멧 네르바 추진기 | Project_CermetNerva | project | SpaceScience | 750 | Project_NervaDrive |
| 로버 추진기 | Project_RoverDrive | project | SpaceScience | 750 | Project_SolidCoreFissionReactorVIII |
| 로렌츠 추진기 | Project_LorentzDrive | project | SpaceScience | 800 | (Project_SolidCoreFissionReactorI OR Project_FuelCellIII) + HighEnergyElectromagneticPropulsion |
| 고성능 VASIMR 추진기 | Project_PonderomotiveVASIMR | project | SpaceScience | 900 | HighEnergyElectromagneticPropulsion + Project_VASIMR |
| 고성능 네르바 추진기 | Project_AdvancedNervaDrive | project | SpaceScience | 1000 | Project_NervaDrive |
| 자동화된 태양광 플랫폼 키트 | Project_AutomatedSolarPlatformKit | project | SpaceScience | 1000 | Project_AutomatedSolarCollector + Project_AutomatedSupplyDepot |
| 심우주 망원경 | Project_DeepSpaceTelescope | project | SpaceScience | 1000 | (Project_OrbitalCore OR Project_SettlementCore) + AdvancedNeuralNetworks + DirectedSpaceResearch + DeepSystemSkywatch + Project_HydraInterrogation + objective:ResearchAlienTechnology + faction:EscapeCouncil |
| 덤보 추진기 | Project_Dumbo | project | SpaceScience | 1000 | Project_SolidCoreFissionReactorII |
| 핵분열 파편 추진기 | Project_FissionFragDrive | project | SpaceScience | 1000 | AdvancedCarbonManipulation + Project_SolidCoreFissionReactorVII |
| 현지 자원 활용 모듈 | Project_ISRUModule | project | SpaceScience | 1000 | OrbitalShipbuilding + InSituResourceUtilization |
| Z-핀치 미세분열 추진기 | Project_Z-pinchMicrofissionDrive | project | SpaceScience | 1000 | ZPinchTechniques + FissionPulseDrives |
| 고성능 공동 추진기 | Project_AdvancedCavityDrive | project | SpaceScience | 1500 | (Project_VaporCoreFissionReactorIII OR Project_GasCoreFissionReactorII) + Project_CavityDrive + SuperconductingMagnets |
| 고성능 세멧 네르바 | Project_AdvancedCermetNerva | project | SpaceScience | 1500 | Project_CermetNerva + Project_Dumbo |
| 입자 추진기 | Project_AdvancedPebbleDrive | project | SpaceScience | 1500 | Project_PebbleDrive + Project_SolidCoreFissionReactorX |
| 고성능 측량 탐사 | Project_AdvancedProspectingSurveys | project | SpaceScience | 1500 | OrbitalShipbuilding + IndustrializationofSpace + Project_MobileSpaceScienceLab |
| 고성능 와류 추진기 | Project_AdvancedVortexDrive | project | SpaceScience | 1500 | Project_VortexDrive + Project_VaporCoreFissionReactorIII |
| 자동화된 핵분열 플랫폼 키트 | Project_AutomatedFissionPlatformKit | project | SpaceScience | 1500 | Project_AutomatedFissionPile + Project_AutomatedSupplyDepot |
| 핵융합 전초기지 키트 | Project_FusionOutpostKit | project | SpaceScience | 1500 | Project_OutpostCore + Project_FusionPile + Project_ConstructionModule |
| 핵융합 플랫폼 키트 | Project_FusionPlatformKit | project | SpaceScience | 1500 | Project_PlatformCore + Project_FusionPile + Project_ConstructionModule |
| 그리드 추진기 | Project_GridDrive | project | SpaceScience | 1500 | (Project_SolidCoreFissionReactorI OR Project_FuelCellIII) + CarbonNanotubes + Project_IonDrive |
| 헬리콘 추진기 | Project_HeliconDrive | project | SpaceScience | 1500 | (Project_SolidCoreFissionReactorII OR Project_MoltenCoreFissionReactorI) + HighEnergyElectromagneticPropulsion |
| 라스 추진기 | Project_LarsDrive | project | SpaceScience | 1500 | Project_MoltenCoreFissionReactorI |
| 전구 추진기 | Project_LightbulbDrive | project | SpaceScience | 1500 | Project_QuartzDrive |
| 페블 추진기 | Project_PebbleDrive | project | SpaceScience | 1500 | Project_SolidCoreFissionReactorIX |
| 정착지 채굴단지 | Project_SettlementMiningComplex | project | SpaceScience | 1500 | Project_SettlementCore + Project_OutpostMiningComplex |
| 우주 과학 연구 센터 | Project_SpaceScienceResearchCenter | project | SpaceScience | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + Project_SpaceScienceLab + DirectedSpaceResearch |
| 와류 추진기 | Project_VortexDrive | project | SpaceScience | 1500 | Project_VaporCoreFissionReactorII |
| 뉴트로늄 미세분열 추진기 | Project_NeutroniumMicrofissionDrive | project | SpaceScience | 2000 | Project_UltracoldNeutronContainment + FissionPulseDrives |
| 파로스 추진기 | Project_PharosDrive | project | SpaceScience | 2000 | Superalloys + Project_GasCoreFissionReactorIII |
| 펄서 추진기 | Project_PulsarDrive | project | SpaceScience | 2000 | (ArcLasers OR ParticleCannon) + Project_NervaDrive + Project_SolidCoreFissionReactorIII |
| 티어드롭 추진기 | Project_TeardropDrive | project | SpaceScience | 2000 | Project_MoltenCoreFissionReactorII |
| 우주 지휘권 위임 | Project_DevolvedSpaceCommand | project | SpaceScience | 2500 | IndustrializationofSpace + AdministrationAlgorithms |
| 중량 덤보 | Project_HeavyDumbo | project | SpaceScience | 2500 | Project_Dumbo + Project_SolidCoreFissionReactorIV |
| 유지보수 절차 개선 | Project_ImprovedMaintenanceProcedures | project | SpaceScience | 2500 | IndustrializationofSpace |
| 연구 캠퍼스 | Project_ResearchCampus | project | SpaceScience | 2500 | (Project_OrbitalCore OR Project_SettlementCore) + QuantumComputing |
| 식민지 채굴단지 | Project_ColonyMiningComplex | project | SpaceScience | 3000 | Project_ColonyCore + Project_SettlementMiningComplex + Superalloys |
| 고성능 펄서 추진기 | Project_AdvancedPulsarDrive | project | SpaceScience | 4000 | SuperconductingMagnets + Project_PulsarDrive + Project_SolidCoreFissionReactorV |
| 고성능 화학 로켓 | Project_AdvancedInterplanetaryRockets | project | SpaceScience | 5000 | AdvancedHydrogenContainment + Project_ImprovedInterplanetaryRockets |
| 반물질 미세분열 추진기 | Project_AntimatterMicrofissionDrive | project | SpaceScience | 5000 | AntimatterContainment + FissionPulseDrives |
| 자동화된 태양광 전초기지 키트 | Project_AutomatedSolarOutpostKit | project | SpaceScience | 5000 | Project_AutomatedSolarCollector + Project_AutomatedMiningComplex |
| 버너 추진기 | Project_BurnerDrive | project | SpaceScience | 5000 | Superalloys + Project_GasCoreFissionReactorII |
| 먼지 플라즈마 추진기 | Project_DustyPlasmaDrive | project | SpaceScience | 5000 | Project_GasCoreFissionReactorI + MagneticNozzles + Project_FissionFragDrive + HighTemperatureSuperconductors |
| 핵분열 회전 추진기 | Project_FissionSpinnerDrive | project | SpaceScience | 5000 | Project_LarsDrive + Project_MoltenCoreFissionReactorII |
| 헬륨-3 광산 | Project_Helium-3Mine | project | SpaceScience | 5000 | Project_RingCore + DeuteriumHelium3Fusion + MissiontoJupiter + SpaceMiningandRefining |
| 극소자기 오리온 추진기 | Project_MinimagOrion | project | SpaceScience | 5000 | Project_Z-pinchMicrofissionDrive |
| 신속한 선박 건조 | Project_RapidShipbuilding | project | SpaceScience | 5000 | ImprovedShipbuildingTechniques + SelfRepairingSoftware |
| 삼중수소 퓨저 추진기 | Project_TritonFusorDrive | project | SpaceScience | 5000 | MagneticNozzles + Project_ElectrostaticConfinementFusionReactorI |
| 삼중수소 원환체 추진기 | Project_TritonTorusDrive | project | SpaceScience | 5000 | MagneticNozzles + Project_FusionTokamakI |
| 자동화된 핵분열 전초기지 키트 | Project_AutomatedFissionOutpostKit | project | SpaceScience | 6500 | Project_AutomatedFissionPile + Project_AutomatedMiningComplex |
| 중수소 퓨저 추진기 | Project_DeuteronFusorDrive | project | SpaceScience | 7500 | MagneticNozzles + Project_ElectrostaticConfinementFusionReactorII |
| 삼중수소 폴리웰 추진기 | Project_TritonPolywellDrive | project | SpaceScience | 7500 | MagneticNozzles + Project_HybridConfinementFusionReactorI |
| 삼중수소 반사 추진기 | Project_TritonReflexDrive | project | SpaceScience | 7500 | MagneticNozzles + Project_MirrorCellFusionReactorI |
| 고성능 극소자기 오리온 추진기 | Project_AdvancedMinimagOrion | project | SpaceScience | 10000 | Project_MinimagOrion |
| 중수소 원환체 추진기 | Project_DeuteronTorusDrive | project | SpaceScience | 10000 | MagneticNozzles + Project_FusionTokamakII |
| 로드스타 핵분열 등 | Project_LodestarFissionLantern | project | SpaceScience | 10000 | MagneticForceManipulation + Project_GasCoreFissionReactorIV |
| 오리온 추진기 | Project_OrionDrive | project | SpaceScience | 10000 | FissionPulseDrives |
| 우주 과학 연구원 | Project_SpaceScienceInstitute | project | SpaceScience | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_SpaceScienceResearchCenter + AppliedArtificialIntelligence |
| 제타 삼중수소 추진기 | Project_ZetaTritonDrive | project | SpaceScience | 10000 | MagneticNozzles + Project_ZPinchFusionReactorI |
| 페가수스 추진기 | Project_PegasusDrive | project | SpaceScience | 12000 | (Project_FissionSpinnerDrive OR Project_TeardropDrive) + Project_MoltenCoreFissionReactorIII |
| 삼중수소 노바 추진기 | Project_TritonNovaDrive | project | SpaceScience | 14000 | MagneticNozzles + Project_InertialConfinementFusionReactorI |
| 중수소 반사 추진기 | Project_DeuteronReflexDrive | project | SpaceScience | 15000 | MagneticNozzles + Project_MirrorCellFusionReactorII |
| 플레어 추진기 | Project_FlareDrive | project | SpaceScience | 15000 | MagneticForceManipulation + Project_GasCoreFissionReactorV |
| 경수소 퓨저 추진기 | Project_ProtiumFusorDrive | project | SpaceScience | 15000 | MagneticNozzles + Project_ElectrostaticConfinementFusionReactorIII |
| 파이어스타 핵분열 등 | Project_FirestarFissionLantern | project | SpaceScience | 20000 | SuperconductingMagnets + Superalloys + Project_GasCoreFissionReactorVI |
| 강화된 거주지 대피소 | Project_HardenedHabShelters | project | SpaceScience | 20000 | TransInterfaceWarfare + Diamondoids + ExtendedSpaceSurvival |
| 헬리온 반사 추진기 | Project_HelionReflexDrive | project | SpaceScience | 20000 | MagneticNozzles + Project_MirrorCellFusionReactorIII |
| 연구 대학 | Project_ResearchUniversity | project | SpaceScience | 20000 | (Project_RingCore OR Project_ColonyCore) + Project_ResearchCampus + IntegratedEarthSpaceEconomy |
| H-오리온 추진기 | Project_AdvancedOrionDrive | project | SpaceScience | 25000 | HeavyPulsedPropulsion + Project_OrionDrive |
| 반물질 펄스 플라즈마 노심 등 | Project_AntimatterPulsedPlasmaCoreLantern | project | SpaceScience | 25000 | AntimatterPropulsion + MagneticNozzles + Project_AntimatterPlasmaCoreReactorI |
| 중수소 노바 등 | Project_DeuteronNovaLantern | project | SpaceScience | 25000 | MagneticNozzles + Project_InertialConfinementFusionReactorII |
| 중수소 폴리웰 추진기 | Project_DeuteronPolywellDrive | project | SpaceScience | 25000 | MagneticNozzles + Project_HybridConfinementFusionReactorII |
| 제타 중수소 추진기 | Project_ZetaDeuteronDrive | project | SpaceScience | 25000 | MagneticNozzles + Project_ZPinchFusionReactorII |
| 헬리온 원한체 등 | Project_HelionTorusLantern | project | SpaceScience | 30000 | MagneticNozzles + Project_FusionTokamakIII |
| 포세이돈 랜턴 | Project_NeutronFluxLantern | project | SpaceScience | 35000 | AdvancedFissionSystems |
| 헬륨 플라스마젯 등 | Project_HelionPlasmajetLantern | project | SpaceScience | 45000 | MagneticNozzles + Project_HybridConfinementFusionReactorIII |
| 반물질 플라즈마 노심 토치 | Project_AntimatterPlasmaCoreTorch | project | SpaceScience | 50000 | AntimatterPropulsion + Project_AntimatterPlasmaCoreReactorII + Project_AntimatterPulsedPlasmaCoreLantern |
| 제타 헬리온 등 | Project_ZetaHelionLantern | project | SpaceScience | 50000 | MagneticNozzles + Project_ZPinchFusionReactorIII |
| 헬리온 노바 등 | Project_HelionNovaLantern | project | SpaceScience | 55000 | MagneticNozzles + Project_InertialConfinementFusionReactorIII |
| 경수소 원환체 등 | Project_ProtiumTorusLantern | project | SpaceScience | 60000 | MagneticNozzles + Project_FusionTokamakV |
| 제타 보레인 등 | Project_ZetaBoraneLantern | project | SpaceScience | 60000 | MagneticNozzles + Project_ZPinchFusionReactorIV |
| 보레인 노바 등 | Project_BoraneNovaLantern | project | SpaceScience | 65000 | MagneticNozzles + Project_InertialConfinementFusionReactorV |
| 보레인 플라스마젯 토치 | Project_BoranePlasmajetTorch | project | SpaceScience | 75000 | MagneticNozzles + Project_HybridConfinementFusionReactorIV |
| 제타 중수소 토치 | Project_ZetaDeuteronTorch | project | SpaceScience | 100000 | MagneticNozzles + Project_FlowStabilizedZPinchFusionReactor |
| 고성능 반물질 플라즈마 노심 토치 | Project_AdvancedAntimatterPlasmaCoreTorch | project | SpaceScience | 120000 | AntimatterPropulsion + Project_AntimatterPlasmaCoreReactorIII + Project_AntimatterPlasmaCoreTorch |
| 헬리온 노바 토치 | Project_HelionNovaTorch | project | SpaceScience | 120000 | MagneticNozzles + Project_InertialConfinementFusionReactorIV |
| 포세이돈 토치 | Project_NeutronFluxTorch | project | SpaceScience | 150000 | Project_NeutronFluxLantern + MagneticNozzles |
| 파이온 토치 | Project_AntimatterBeamCoreTorch | project | SpaceScience | 200000 | AntimatterPropulsion + MagneticNozzles + Project_AntimatterBeamCoreReactor |
| 경수소 노바 토치 | Project_ProtiumNovaTorch | project | SpaceScience | 200000 | MagneticNozzles + Project_InertialConfinementFusionReactorVI |
| 경수소 변환기 토치 | Project_ProtiumConverterTorch | project | SpaceScience | 1000000 | Project_ProtiumNovaTorch + Project_InertialConfinementFusionReactorVII |
| Alien Advanced Master Project | Project_AlienAdvancedMasterProject | project | Xenology | -1 | Project_AlienMasterProject + faction:AlienCouncil |
| Alien Master Project | Project_AlienMasterProject | project | Xenology | -1 | faction:AlienCouncil |
| 외계인의 흔적 | Project_TheirSignatures | project | Xenology | 25 | objective:InvestigateAlienCrashdown |
| 외계인의 방식 | Project_TheirMethods | project | Xenology | 300 | objective:InvestigateAlienAbductions |
| 외계학 연구실 | Project_XenologyLab | project | Xenology | 300 | (Project_PlatformCore OR Project_OutpostCore) + WeAreNotAlone + Project_TheirSignatures |
| 외계 식물군 | Project_AlienFlora | project | Xenology | 500 | milestone:DetectXenoforming |
| 외계인의 작전 | Project_TheirOperations | project | Xenology | 500 | objective:InvestigateEnthrallMission |
| 외계 과학 연구 센터 | Project_XenoscienceResearchCenter | project | Xenology | 1500 | (Project_OrbitalCore OR Project_SettlementCore) + Project_XenologyLab + DirectedSpaceResearch |
| 외계인의 움직임 | Project_TheirMovements | project | Xenology | 2000 | Project_TheirOperations |
| 외계인의 기원 | Project_TheirOrigin | project | Xenology | 2000 | Project_TheirSignatures + DeepSystemSkywatch |
| 외계인 대역폭 | Project_AlienBandwidth | project | Xenology | 2500 | Project_HydraDiplomacy + Project_SubmitVictory + faction:SubmitCouncil |
| 침략자에 대한 유화책 | Project_AppeaseVictory | project | Xenology | 2500 | Project_TheirOperations + faction:AppeaseCouncil |
| 지구 정화 | Project_DestroyVictory | project | Xenology | 2500 | Project_TheirMethods + faction:DestroyCouncil |
| 종결을 위한 수단 | Project_ExploitVictory | project | Xenology | 2500 | Project_Pherocytes + faction:ExploitCouncil |
| 신속대응팀 | Project_RapidResponseTeams | project | Xenology | 2500 | TerrestrialMilitaryScience + milestone:TargetedByTerrorMission + faction:ResistCouncil/DestroyCouncil/ExploitCouncil/EscapeCouncil/CooperateCouncil |
| 지구를 지켜라 | Project_ResistVictory | project | Xenology | 2500 | Project_TheirOperations + faction:ResistCouncil |
| 낙원으로 가는 길 | Project_SubmitVictory | project | Xenology | 2500 | Project_TheirMethods + faction:SubmitCouncil |
| 워도그 부검 | Project_WarDogNecropsy | project | Xenology | 2500 | Biotechnology + milestone:AccessWarDogCorpus |
| 히드라 격리 | Project_AlienContainment | project | Xenology | 5000 | Project_Pherocytes |
| 외계인-적응형 ECM | Project_AlienECM | project | Xenology | 5000 | Project_ECM1 + Project_TheirComputers + Project_TheirWarships + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 고향 떠나기 | Project_EscapeVictory | project | Xenology | 5000 | Project_TheirOrigin + faction:EscapeCouncil |
| 고위 인사 보호 | Project_ExecutiveProtection | project | Xenology | 5000 | Project_Pherocytes + ArrivalSecurity + faction:ResistCouncil/DestroyCouncil/ExploitCouncil/EscapeCouncil/CooperateCouncil/AppeaseCouncil |
| 그리핀 부검 | Project_GriffinAutopsy | project | Xenology | 5000 | Biotechnology + milestone:AccessGriffinCorpus |
| 히드라 생물학 | Project_HydraBiology | project | Xenology | 5000 | objective:AccessHydraCorpus |
| 히드라 직접 지원 네트워크 | Project_NegotiatedSupportChannel | project | Xenology | 5000 | Project_HydraDiplomacy + IndustrializationofSpace + faction:AppeaseCouncil |
| 페로사이트 | Project_Pherocytes | project | Xenology | 5000 | (Project_HydraBiology OR Project_CoexistencePact) |
| 히드라 직접 지원 네트워크 | Project_ProxySupportChannel | project | Xenology | 5000 | Project_HydraDiplomacy + MissionToSpace + faction:SubmitCouncil |
| 샐러맨더 부검 | Project_SalamanderAutopsy | project | Xenology | 5000 | Biotechnology + milestone:AccessSalamanderCorpus + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil |
| 보안 조치 | Project_SecurityMeasures | project | Xenology | 5000 | Project_TheirOperations + AdvancedNeuralNetworks + ArrivalSecurity + faction:ResistCouncil/DestroyCouncil/ExploitCouncil/EscapeCouncil/CooperateCouncil/AppeaseCouncil |
| 외계 컴퓨터 | Project_TheirComputers | project | Xenology | 5000 | Project_TheirTechnology + QuantumComputing |
| 그들의 요구 | Project_TheirDemands | project | Xenology | 5000 | Project_HydraDiplomacy + faction:AppeaseCouncil/CooperateCouncil/SubmitCouncil |
| 외계식물 고엽제 | Project_XenofloraDefoliants | project | Xenology | 5000 | Project_AlienFlora + milestone:DetectXenoforming + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 외계 관광 | Project_Xenotourism | project | Xenology | 5000 | SpaceTourism + Project_XenofaunaHarmony + faction:SubmitCouncil/AppeaseCouncil |
| 페로사이트로 향상된 심문 | Project_Pherocyte-EnhancedInterrogations | project | Xenology | 8000 | ArrivalPsychology + AugmentedReality + Project_PherocyteMastery + faction:ExploitCouncil |
| 외계 군대 분석 | Project_AlienArmyAnalysis | project | Xenology | 10000 | NetworkedGlobalDefense + Project_TheirTechnology + milestone:AlienArmyDestroyed |
| 조정된 자원 지원 | Project_CoordinatedResourceSupport | project | Xenology | 10000 | Project_ProxySupportChannel + SpaceCommerce + Project_SubmitVictory + faction:SubmitCouncil |
| 지정된 자원 채널 | Project_DirectedResourceChannel | project | Xenology | 10000 | Project_NegotiatedSupportChannel + SpaceCommerce + Project_AppeaseVictory + faction:AppeaseCouncil |
| 그리핀 심문 | Project_GriffinInterrogation | project | Xenology | 10000 | Biotechnology + Project_Pherocytes + milestone:AccessLiveGriffin |
| 대히드라 외교 | Project_HydraDiplomacy | project | Xenology | 10000 | Project_HydraLanguage + faction:AppeaseCouncil/CooperateCouncil/SubmitCouncil |
| 히드라 언어 | Project_HydraLanguage | project | Xenology | 10000 | (objective:CaptureAHydra OR objective:ContactTheAliens) |
| 아이디어 주입 | Project_IdeaViruses | project | Xenology | 10000 | TargetedBiologicalWarfare + AppliedArtificialIntelligence + Project_PherocyteMastery + faction:ExploitCouncil |
| 거대 외계 동물군 부검 | Project_MegafaunaNecropsy | project | Xenology | 10000 | Biotechnology + milestone:AccessAlienMegafauna |
| 페로사이트 방출기 | Project_PherocyteEmitter | project | Xenology | 10000 | MindandMachine + Project_Pherocytes + Project_NeuralEngineering |
| 페로사이트 책임 이론 | Project_PherocyteLiabilityTheory | project | Xenology | 10000 | ArrivalLaw + Project_Pherocytes + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 페로사이트 격리 프로토콜 | Project_PherocyteQuarantineProtocols | project | Xenology | 10000 | PredictiveGenetics + ArrivalMassCommunications + Project_Pherocytes + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 페로사이트 스캐너 | Project_PherocyteScanners | project | Xenology | 10000 | MolecularAssemblers + Project_Pherocytes + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 외계 소형 화기 역설계 | Project_Reverse-EngineeredAlienSmallArms | project | Xenology | 10000 | Project_TheirTechnology + milestone:AccessAlienTech |
| 샐러맨더 심문 | Project_SalamanderInterrogation | project | Xenology | 10000 | Biotechnology + Project_Pherocytes + milestone:AccessLiveSalamander |
| 전략적 기만술 | Project_StrategicDeception | project | Xenology | 10000 | ArrivalSecurity + Project_HydraInterrogation + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 외계 국가 | Project_TheAlienNation | project | Xenology | 10000 | Project_HydraDiplomacy + faction:SubmitCouncil |
| 유일한 진실의 길 | Project_TheOneTruePath | project | Xenology | 10000 | Project_SubmitVictory + Project_TheAlienNation + Project_TheirDemands + faction:SubmitCouncil |
| 외계 기술 | Project_TheirTechnology | project | Xenology | 10000 | Project_TheirSignatures + milestone:AccessAlienTech |
| 외계인의 군함 | Project_TheirWarships | project | Xenology | 10000 | Project_TheirTechnology + objective:SalvageAlienWarship |
| 외계 동물군과의 조화 | Project_XenofaunaHarmony | project | Xenology | 10000 | Project_AlienFlora + milestone:AlienMegafaunaSpawns + faction:SubmitCouncil/AppeaseCouncil |
| 외계 과학 연구원 | Project_XenoscienceInstitute | project | Xenology | 10000 | (Project_RingCore OR Project_ColonyCore) + Project_XenoscienceResearchCenter + Project_Exotics + AppliedArtificialIntelligence |
| 외계인 레드 팀 구성 | Project_AlienRedTeaming | project | Xenology | 15000 | MindandMachine + Project_HydraInterrogation + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil |
| 마스키로브카 전술 | Project_Maskirovka | project | Xenology | 15000 | QuantumEncryption + Project_StrategicDeception + Project_TheirTechnology + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 보안 책임 연쇄 | Project_SecurityAccountabilityChaining | project | Xenology | 15000 | ArrivalSecurity + Project_PherocyteScanners + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 외계 로봇공학 | Project_TheirRobotics | project | Xenology | 15000 | Project_TheirComputers |
| 외계인 제거 | Project_XenologicalCulls | project | Xenology | 15000 | TargetedBiologicalWarfare + Project_XenofloraDefoliants + Project_MegafaunaNecropsy + milestone:AccessAlienMegafauna + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 새로운 보금자리 | Project_ANewHome | project | Xenology | 20000 | objective:BeginTheSearch + faction:EscapeCouncil |
| 고급 외계 생물학 모니터링 | Project_AdvancedXenologicalMonitoring | project | Xenology | 20000 | AdministrationAlgorithms + Project_MegafaunaNecropsy + Project_AlienFlora + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 공동체 치안 유지 드론 | Project_CommunityPolicingDrones | project | Xenology | 20000 | NextGenerationAerospace + NetworkedGlobalDefense + Project_Pherocytes + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 엑조틱 물질 | Project_Exotics | project | Xenology | 20000 | (Project_TheirTechnology OR Project_HydraDiplomacy) + (objective:SalvageAlienWarship OR objective:ContactTheAliens) |
| 헌터-킬러 전술 부대 | Project_Hunter-KillerTacticalUnits | project | Xenology | 20000 | NetworkedGlobalDefense + Project_SalamanderInterrogation + Project_Reverse-EngineeredAlienSmallArms + Project_CounteralienOperationsTeams + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil |
| 히드라 심문 | Project_HydraInterrogation | project | Xenology | 20000 | Project_HydraLanguage + Project_AlienContainment + objective:CaptureAHydra + faction:CooperateCouncil/DestroyCouncil/EscapeCouncil/ExploitCouncil/ResistCouncil |
| 전술적 혼란 유도 | Project_OperationalMisdirection | project | Xenology | 20000 | FleetLogistics + Project_StrategicDeception + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 페로사이트 노출 네트워크 추적 | Project_PherocyteExposureNetworkTracing | project | Xenology | 20000 | WhiteCollarAutomation + Project_Pherocytes + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 페로사이트 대량 방출기 | Project_PherocyteMassEmitter | project | Xenology | 20000 | Project_PherocyteMastery + Project_PherocyteEmitter |
| 정책입안자 행동분석 | Project_PolicymakerBehaviorialAnalysis | project | Xenology | 20000 | ArrivalGovernance + WhiteCollarAutomation + Project_Pherocytes + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 납치 예측 모델링 | Project_PredictiveAbductionModeling | project | Xenology | 20000 | WhiteCollarAutomation + Project_HydraInterrogation + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 지역 보안 점검 | Project_RegionalSecuritySweeps | project | Xenology | 20000 | NetworkedGlobalDefense + Project_PherocyteDeconOperations + Project_RapidResponseTeams + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil |
| 그들의 목적 | Project_TheirPurpose | project | Xenology | 20000 | Project_HydraInterrogation |
| 그들의 약점 | Project_TheirWeakness | project | Xenology | 20000 | Project_HydraInterrogation + faction:DestroyCouncil/CooperateCouncil |
| 공존 협정 | Project_CoexistencePact | project | Xenology | 25000 | Project_AppeaseVictory + Project_TheirDemands + faction:AppeaseCouncil |
| 협조적인 해결책 | Project_CooperateVictory | project | Xenology | 25000 | Project_TheirOperations + faction:CooperateCouncil |
| 엑조틱 하이브리드 시스템 | Project_ExoticHybridSystems | project | Xenology | 25000 | QuantumComputing + Project_Exotics |
| 산업 지원 협정 | Project_IndustrialSupportAgreement | project | Xenology | 25000 | Project_DirectedResourceChannel + IntegratedEarthSpaceEconomy + faction:AppeaseCouncil |
| 페로사이트 오염제거 작전 | Project_PherocyteDeconOperations | project | Xenology | 25000 | DesignerLifeforms + ArrivalSecurity + Project_PherocyteScanners + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 마지막 돌격 | Project_TheFinalAssault | project | Xenology | 25000 | Project_ResistVictory + Project_TheChokePoint + faction:ResistCouncil |
| 전장의 페로사이트 오염 제거 | Project_BattlefieldPherocyteDecontamination | project | Xenology | 30000 | NetworkedGlobalDefense + Project_PherocyteDeconOperations + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 전장의 페로사이트 배치 | Project_BattlefieldPherocyteDeployment | project | Xenology | 30000 | Project_PherocyteMastery + faction:ExploitCouncil |
| 페로사이트 저항 | Project_PherocyteResistance | project | Xenology | 30000 | Project_HydraInterrogation + Project_Pherocytes |
| 공공 행동 모니터링 | Project_PublicBehaviorialMonitoring | project | Xenology | 30000 | ArrivalCulture + Cybernetics + Project_Pherocytes + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 웜홀 | Project_Wormholes | project | Xenology | 30000 | Project_Exotics + Project_HydraInterrogation + Project_TheirOrigin + faction:CooperateCouncil/DestroyCouncil/EscapeCouncil/ExploitCouncil/ResistCouncil |
| 페로사이트 접종 | Project_PherocyteInoculations | project | Xenology | 35000 | TransformPhages + Project_MegafaunaNecropsy + Project_GriffinInterrogation + Project_WarDogNecropsy + Project_SalamanderInterrogation + faction:DestroyCouncil/ResistCouncil/ExploitCouncil/CooperateCouncil/EscapeCouncil/AppeaseCouncil |
| 초크 포인트 | Project_TheChokePoint | project | Xenology | 40000 | Project_Wormholes + Project_TheirPurpose + faction:CooperateCouncil/DestroyCouncil/ExploitCouncil/ResistCouncil |
| 대히드라 생물 전쟁 | Project_HydraBiowarfare | project | Xenology | 50000 | Project_TheirWeakness + Project_PherocyteResistance + faction:DestroyCouncil |
| 통합된 인간-히드라 경제 | Project_IntegratedHuman-HydraEconomy | project | Xenology | 50000 | Project_CoordinatedResourceSupport + IntegratedEarthSpaceEconomy + faction:SubmitCouncil |
| 하이브 처치 | Project_KilltheHive | project | Xenology | 50000 | Project_DestroyVictory + Project_TheChokePoint + Project_HydraBiowarfare + faction:DestroyCouncil |
| 거대 외계 동물군 지배 | Project_MegafaunaMastery | project | Xenology | 50000 | Project_PherocyteMastery + Project_MegafaunaNecropsy + Project_AlienFlora + faction:ExploitCouncil |
| 페로사이트 장악 | Project_PherocyteMastery | project | Xenology | 50000 | Project_PherocyteResistance + faction:ExploitCouncil |
| 위대한 여정을 앞두고 | Project_TheGreatJourney | project | Xenology | 50000 | Project_EscapeVictory + Project_ExoticHybridSystems + Project_ANewHome + faction:EscapeCouncil |
| 지배자를 노예로 | Project_EnslavetheMasters | project | Xenology | 75000 | Project_ExploitVictory + Project_TheChokePoint + Project_PherocyteMastery + faction:ExploitCouncil |
| 영원한 평화 | Project_APermanentPeace | project | Xenology | 100000 | Project_CooperateVictory + Project_PherocyteResistance + Project_TheirDemands + Project_TheirWeakness + Project_TheChokePoint + faction:CooperateCouncil |
