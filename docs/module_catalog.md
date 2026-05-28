# Terra Invicta Hab Module Catalog

Generated from `TerraInvicta_Data/StreamingAssets/Templates/TIHabModuleTemplate.json`.

This file is generated. Rebuild it with:

```powershell
python .\tools\build_module_catalog.py
```

Important interpretation notes:

- `Income/mo` is template income only. Mine output still needs the hab site's resource deposits and faction mining modifiers.
- `Support/mo` includes module crew salary/water/volatiles support before hab-level farm discounts.
- Actual recommendations must also evaluate available power, module slot legality, construction state, faction effects, and adviser bonuses from the save.

Module count: `156` total, `110` normally buildable human modules.

## High-Value Recommendation Inputs

| Module | dataName | T | Type | Tags | Power | Crew | MC | CP | Income/mo | Support/mo | Project |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| 관리 노드 | AdministrationNode | 1 | Any | controlPointCap, efficiency, leoOnlyCpCap, powerConsumer, upkeep | -10 | 40 | 0 | 4 |  | Money:10.333333, Boost:1, Water:1.166667, Volatiles:1.196667, Metals:0.03, NobleMetals:0.03 | Project_AdministrationNode |
| 자동화된 핵분열 원자로 | AutomatedFissionPile | 1 | Any | powerProducer, upkeep | 20 | 0 | 0 | 0 |  | Water:0.5, Fissiles:0.05 | Project_AutomatedFissionPile |
| 자동화된 태양광 수집기 | AutomatedSolarCollector | 1 | Any | powerProducer | 20 | 0 | 0 | 0 |  |  | Project_AutomatedSolarCollector |
| 에너지 연구실 | EnergyLab | 1 | Any | powerConsumer, research, upkeep | -10 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:1.0875, Fissiles:0.001 | Project_EnergyLab |
| 핵분열 원자로 | FissionPile | 1 | Any | powerProducer, upkeep | 20 | 4 | 0 | 0 |  | Money:2.033333, Water:0.616667, Volatiles:0.366667, Fissiles:0.05 | Project_FissionPile |
| 핵융합 원자로 | FusionPile | 1 | Any | powerProducer, upkeep | 40 | 5 | 0 | 0 |  | Money:3.041667, Water:1.145833, Volatiles:0.645833, Fissiles:0.02 | Project_FusionPile |
| 고출력 핵분열 원자로 | HeavyFissionPile | 1 | Any | powerProducer, upkeep | 30 | 4 | 0 | 0 |  | Money:3.033333, Water:0.616667, Volatiles:0.366667, Fissiles:0.075 | Project_HeavyFissionPile |
| 고출력 핵융합 원자로 | HeavyFusionPile | 1 | Any | powerProducer, upkeep | 70 | 10 | 0 | 0 |  | Money:5.083333, Water:1.291667, Volatiles:0.791667, Metals:0.1, NobleMetals:0.1, Fissiles:0.02 | Project_HeavyFusionPile |
| 정보 과학 연구실 | InformationScienceLab | 1 | Any | powerConsumer, research, upkeep | -10 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_InformationScienceLab |
| 생명 과학 연구실 | LifeScienceLab | 1 | Any | powerConsumer, research, upkeep | -5 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.5875, Volatiles:0.5875 | Project_LifeScienceLab |
| 재료 연구실 | MaterialsLab | 1 | Any | powerConsumer, research, upkeep | -6 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875, Metals:0.1, NobleMetals:0.1 | Project_MaterialsLab |
| 군사 과학 연구실 | MilitaryScienceLab | 1 | Any | powerConsumer, research, upkeep | -5 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_MilitaryScienceLab |
| 사회 과학 연구실 | SocialScienceLab | 1 | Any | powerConsumer, research, upkeep | -4 | 3 | 0 | 0 | Research:5 | Money:3.025, Water:0.0875, Volatiles:0.0875 | Project_SocialScienceLab |
| 태양광 수집기 | SolarCollector | 1 | Any | powerProducer, upkeep | 20 | 1 | 0 | 0 |  | Money:1.008333, Water:0.029167, Volatiles:0.029167 | Project_SolarCollector |
| 우주 정거장 | SpaceDock | 1 | Any | powerConsumer, resupply, shipyard, upkeep | -20 | 40 | 0 | 0 |  | Money:0.333333, Water:1.166667, Volatiles:1.166667, Metals:1, NobleMetals:0.1 | Project_SpaceDock |
| 우주 과학 연구실 | SpaceScienceLab | 1 | Any | powerConsumer, research, upkeep | -5 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_SpaceScienceLab |
| 외계학 연구실 | XenologyLab | 1 | Any | powerConsumer, research, upkeep | -10 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_XenologyLab |
| 자동화된 채굴단지 | AutomatedMiningComplex | 1 | Base | mine, powerConsumer, upkeep | -12 | 0 | 0 | 0 |  | Water:2, Volatiles:0.5 | Project_AutomatedMiningComplex |
| 자동화된 전초기지 코어 | AutomatedOutpostCore | 1 | Base | core, mcConsumer | 0 | 0 | -1 | 0 | MissionControl:-1 |  | Project_AutomatedOutpostCore |
| 전초기지 코어 | OutpostCore | 1 | Base | core, mcConsumer, upkeep | 0 | 5 | -2 | 0 | MissionControl:-2 | Money:3.041667, Water:0.145833, Volatiles:0.145833 | Project_OutpostCore |
| 전초기지 채굴단지 | OutpostMiningComplex | 1 | Base | mine, powerConsumer, upkeep | -10 | 12 | 0 | 0 |  | Money:6.1, Water:2.35, Volatiles:0.85 | Project_OutpostMiningComplex |
| 반물질 포획기 | AntimatterTrap | 1 | Station | powerConsumer, research, upkeep | -5 | 2 | 0 | 0 | Research:5 | Money:2.016667, Water:0.058333, Volatiles:0.058333, Metals:0.1, NobleMetals:0.03 | Project_AntimatterTrap |
| 자동화된 플랫폼 코어 | AutomatedPlatformCore | 1 | Station | core, mcConsumer | 0 | 0 | -1 | 0 | MissionControl:-1 |  | Project_AutomatedPlatformCore |
| 기후 연구실 | ClimateLab | 1 | Station | powerConsumer, research, upkeep | -5 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_ClimateLab |
| 입자 충돌기 | ParticleCollider | 1 | Station | powerConsumer, research, upkeep | -100 | 10 | 0 | 0 | Research:2, Antimatter:0.0001 | Money:6.083333, Water:2.291667, Volatiles:2.291667, Metals:1, NobleMetals:1, Fissiles:1 | Project_ParticleCollider |
| 플랫폼 코어 | PlatformCore | 1 | Station | core, mcConsumer, upkeep | 0 | 3 | -2 | 0 | MissionControl:-2 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_PlatformCore |
| 관리 타워 | AdministrationTower | 2 | Any | controlPointCap, efficiency, leoOnlyCpCap, mcProducer, powerConsumer, upkeep | -40 | 200 | 1 | 12 | MissionControl:1 | Money:31.666667, Boost:4, Water:5.833333, Volatiles:5.933333, Metals:0.1, NobleMetals:0.1 | Project_AdministrationTower |
| 심우주 망원경 | DeepSpaceTelescope | 2 | Any | powerConsumer, research, upkeep | -20 | 15 | 0 | 0 | Research:5 | Money:3.125, Water:0.4375, Volatiles:0.4375 | Project_DeepSpaceTelescope |
| 에너지 연구 센터 | EnergyResearchCenter | 2 | Any | powerConsumer, research, upkeep | -40 | 20 | 0 | 0 | Research:10 | Money:6.166667, Water:0.583333, Volatiles:3.583333, Metals:0.1, NobleMetals:0.1, Fissiles:0.005 | Project_EnergyResearchCenter |
| 핵분열 반응로 배열 | FissionReactorArray | 2 | Any | powerProducer, upkeep | 85 | 20 | 0 | 0 |  | Money:6.166667, Water:2.583333, Volatiles:1.583333, Fissiles:0.2 | Project_FissionReactorArray |
| 핵융합 반응로 배열 | FusionReactorArray | 2 | Any | powerProducer, upkeep | 170 | 25 | 0 | 0 |  | Money:10.208333, Water:3.729167, Volatiles:2.729167, Fissiles:0.05 | Project_FusionReactorArray |
| 고출력 핵분열 반응로 배열 | HeavyFissionReactorArray | 2 | Any | powerProducer, upkeep | 128 | 20 | 0 | 0 |  | Money:8.166667, Water:2.583333, Volatiles:1.583333, Fissiles:0.3 | Project_HeavyFissionReactorArray |
| 고출력 핵융합 반응로 배열 | HeavyFusionReactorArray | 2 | Any | powerProducer, upkeep | 300 | 50 | 0 | 0 |  | Money:12.416667, Water:4.458333, Volatiles:3.458333, Metals:0.5, NobleMetals:0.5, Fissiles:0.08 | Project_HeavyFusionReactorArray |
| 정보 과학 연구 센터 | InformationScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -40 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:1.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_InformationScienceResearchCenter |
| 생명 과학 연구 센터 | LifeScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -20 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:1.729167, Volatiles:1.729167 | Project_LifeScienceResearchCenter |
| 재료 연구 센터 | MaterialsResearchCenter | 2 | Any | powerConsumer, research, upkeep | -24 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:1.729167, Volatiles:1.729167, Metals:1, NobleMetals:0.5 | Project_MaterialsResearchCenter |
| 군사 과학 연구 센터 | MilitaryScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -20 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:0.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_MilitaryScienceResearchCenter |
| 관제소 | OperationsCenter | 2 | Any | mcProducer, powerConsumer, upkeep | -100 | 200 | 4 | 0 | MissionControl:4 | Money:31.666667, Water:5.833333, Volatiles:10.833333, Metals:5, NobleMetals:2.5 | Project_OperationsCenter |
| 연구 캠퍼스 | ResearchCampus | 2 | Any | mcConsumer, powerConsumer, research, upkeep | -50 | 200 | -1 | 0 | Research:60, MissionControl:-1 | Money:31.666667, Water:8.833333, Volatiles:8.833333 | Project_ResearchCampus |
| 조선소 | Shipyard | 2 | Any | powerConsumer, resupply, shipyard, upkeep | -80 | 120 | 0 | 0 |  | Money:1, Water:3.5, Volatiles:3.5, Metals:3, NobleMetals:0.5 | Project_Shipyard |
| 스컹크웍스 | SkunkWorks | 2 | Any | powerConsumer, research, upkeep | -30 | 50 | 0 | 0 | Projects:1 | Money:10.416667, Water:1.458333, Volatiles:4.458333, Metals:3, NobleMetals:0.3 | Project_SkunkWorks |
| 사회과학 연구 센터 | SocialScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -16 | 25 | 0 | 0 | Research:10 | Money:8.208333, Water:0.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_SocialScienceResearchCenter |
| 태양광 발전 배열 | SolarArray | 2 | Any | powerProducer, upkeep | 80 | 5 | 0 | 0 |  | Money:3.041667, Water:0.145833, Volatiles:0.145833 | Project_SolarArray |
| 우주 과학 연구 센터 | SpaceScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -20 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:0.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_SpaceScienceResearchCenter |
| 외계 과학 연구 센터 | XenoscienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -40 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:0.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_XenoscienceResearchCenter |
| 정착지 코어 | SettlementCore | 2 | Base | core, mcConsumer, upkeep | 0 | 25 | -3 | 0 | MissionControl:-3 | Money:10.208333, Water:0.729167, Volatiles:0.729167 | Project_SettlementCore |
| 정착지 채굴단지 | SettlementMiningComplex | 2 | Base | mine, powerConsumer, upkeep | -40 | 60 | 0 | 0 |  | Money:30.5, Water:6.75, Volatiles:3.75 | Project_SettlementMiningComplex |
| 반물질 수확기 | AntimatterHarvester | 2 | Station | powerConsumer, research, upkeep | -20 | 10 | 0 | 0 | Research:10 | Money:5.083333, Water:0.291667, Volatiles:0.291667, Metals:0.5, NobleMetals:0.1 | Project_AntimatterHarvester |
| 원자파괴장치 | Atomsmasher | 2 | Station | powerConsumer, research, upkeep | -250 | 20 | 0 | 0 | Research:5, Antimatter:0.01 | Money:20.166667, Water:10.583333, Volatiles:10.583333, Metals:5, NobleMetals:5, Fissiles:3 | Project_Atomsmasher |
| 기후 연구 센터 | ClimateResearchCenter | 2 | Station | powerConsumer, research, upkeep | -20 | 15 | 0 | 0 | Research:10 | Money:6.125, Water:0.4375, Volatiles:0.5375, Metals:0.1, NobleMetals:0.1 | Project_ClimateResearchCenter |
| 궤도 거주지 코어 | OrbitalCore | 2 | Station | core, mcConsumer, upkeep | 0 | 15 | -3 | 0 | MissionControl:-3 | Money:10.125, Water:0.4375, Volatiles:0.4375 | Project_OrbitalCore |
| 관리 복합단지 | AdministrationComplex | 3 | Any | controlPointCap, efficiency, leoOnlyCpCap, mcProducer, powerConsumer, upkeep | -160 | 1000 | 2 | 30 | MissionControl:2 | Money:98.333333, Boost:12, Water:29.166667, Volatiles:29.666667, Metals:0.5, NobleMetals:0.5 | Project_AdministrationComplex |
| 지휘 센터 | CommandCenter | 3 | Any | mcProducer, powerConsumer, upkeep | -300 | 1000 | 10 | 0 | MissionControl:10 | Money:108.333333, Water:29.166667, Volatiles:39.166667, Metals:10, NobleMetals:5 | Project_CommandCenter |
| 에너지 연구원 | EnergyInstitute | 3 | Any | powerConsumer, research, upkeep | -120 | 100 | 0 | 0 | Research:15 | Money:18.833333, Water:2.916667, Volatiles:12.916667, Metals:0.5, NobleMetals:0.5, Fissiles:0.01 | Project_EnergyInstitute |
| 핵분열 반응로 농장 | FissionReactorFarm | 3 | Any | powerProducer, upkeep | 250 | 100 | 0 | 0 |  | Money:18.833333, Water:8.916667, Volatiles:5.916667, Fissiles:0.5 | Project_FissionReactorFarm |
| 주조소 | Foundry | 3 | Any | powerConsumer, research, upkeep | -90 | 250 | 0 | 0 | Projects:2 | Money:32.083333, Water:7.291667, Volatiles:17.291667, Metals:10, NobleMetals:1 | Project_Foundry |
| 핵융합 반응로 농장 | FusionReactorFarm | 3 | Any | powerProducer, upkeep | 500 | 125 | 0 | 0 |  | Money:31.041667, Water:13.645833, Volatiles:9.645833, Fissiles:0.1 | Project_FusionReactorFarm |
| 고출력 핵분열 반응로 농장 | HeavyFissionReactorFarm | 3 | Any | powerProducer, upkeep | 375 | 100 | 0 | 0 |  | Money:24.833333, Water:8.916667, Volatiles:5.916667, Fissiles:0.75 | Project_HeavyFissionReactorFarm |
| 고출력 핵융합 반응로 농장 | HeavyFusionReactorFarm | 3 | Any | powerProducer, upkeep | 900 | 150 | 0 | 0 |  | Money:37.25, Water:14.375, Volatiles:10.375, Metals:1, NobleMetals:1, Fissiles:0.2 | Project_HeavyFusionReactorFarm |
| 정보 과학 연구원 | InformationScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -120 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:6.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_InformationScienceInstitute |
| 생명 과학 연구원 | LifeScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -60 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:6.645833, Volatiles:6.645833 | Project_LifeScienceInstitute |
| 재료 연구원 | MaterialsInstitute | 3 | Any | powerConsumer, research, upkeep | -72 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:6.645833, Volatiles:6.645833, Metals:3, NobleMetals:1.5 | Project_MaterialsInstitute |
| 군사 과학 연구원 | MilitaryScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -60 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:3.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_MilitaryScienceInstitute |
| 연구 대학 | ResearchUniversity | 3 | Any | mcConsumer, powerConsumer, research, upkeep | -150 | 1000 | -2 | 0 | Research:200, MissionControl:-2 | Money:108.333333, Water:39.166667, Volatiles:39.166667 | Project_ResearchUniversity |
| 사회 과학 연구원 | SocialScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -48 | 125 | 0 | 0 | Research:15 | Money:25.041667, Water:3.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_SocialScienceInstitute |
| 태양광 농장 | SolarFarm | 3 | Any | powerProducer, upkeep | 240 | 25 | 0 | 0 |  | Money:5.208333, Water:0.729167, Volatiles:0.729167 | Project_SolarFarm |
| 우주 과학 연구원 | SpaceScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -60 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:3.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_SpaceScienceInstitute |
| 스페이스웍스 | Spaceworks | 3 | Any | powerConsumer, resupply, shipyard, upkeep | -240 | 400 | 0 | 0 |  | Money:3.333333, Water:11.666667, Volatiles:11.666667, Metals:10, NobleMetals:1 | Project_Spaceworks |
| 외계 과학 연구원 | XenoscienceInstitute | 3 | Any | powerConsumer, research, upkeep | -120 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:3.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_XenoscienceInstitute |
| 식민지 코어 | ColonyCore | 3 | Base | core, mcConsumer, upkeep | 0 | 125 | -4 | 0 | MissionControl:-4 | Money:21.041667, Water:3.645833, Volatiles:3.645833 | Project_ColonyCore |
| 식민지 채굴단지 | ColonyMiningComplex | 3 | Base | mine, powerConsumer, upkeep | -200 | 200 | 0 | 0 |  | Money:61.666667, Water:20.833333, Volatiles:11.833333 | Project_ColonyMiningComplex |
| 반물질 농장 | AntimatterFarm | 3 | Station | powerConsumer, research, upkeep | -80 | 50 | 0 | 0 | Research:15 | Money:10.416667, Water:1.458333, Volatiles:1.458333, Metals:1.5, NobleMetals:1 | Project_AntimatterFarm |
| 기후 연구원 | ClimateInstitute | 3 | Station | powerConsumer, research, upkeep | -60 | 75 | 0 | 0 | Research:15 | Money:20.625, Water:2.1875, Volatiles:2.6875, Metals:0.5, NobleMetals:0.5 | Project_ClimateInstitute |
| 헬륨-3 광산 | Helium-3Mine | 3 | Station | mcConsumer, powerConsumer, upkeep | -300 | 75 | -3 | 0 | MissionControl:-3 | Money:30.625, Water:4.1875, Volatiles:4.1875, Metals:10, NobleMetals:1.5 | Project_Helium-3Mine |
| 성간 발사 시설 | InterstellarLaunchingLaser | 3 | Station | mcConsumer, powerConsumer, upkeep | -5000 | 80 | -20 | 0 | MissionControl:-20 | Money:20.666667, Water:2.333333, Volatiles:2.333333 | Project_InterstellarLaunchingLaser |
| 링형 거주지 코어 | RingCore | 3 | Station | core, mcConsumer, upkeep | 0 | 75 | -4 | 0 | MissionControl:-4 | Money:20.625, Water:2.1875, Volatiles:2.1875 | Project_RingCore |
| 센티넬 복합단지 | SentinelComplex | 3 | Station | mcConsumer, powerConsumer, upkeep | -150 | 100 | -1 | 0 | MissionControl:-1 | Money:20.833333, Water:2.916667, Volatiles:2.916667 | Project_SentinelComplex |
| 초대형 입자 가속기 | Supercollider | 3 | Station | powerConsumer, research, upkeep | -750 | 100 | 0 | 0 | Research:10, Antimatter:0.1 | Money:120.833333, Water:32.916667, Volatiles:32.916667, Metals:20, NobleMetals:20, Fissiles:10 | Project_Supercollider |

## All Normally Buildable Human Modules

| Module | dataName | T | Type | Tags | Power | Crew | MC | CP | Income/mo | Support/mo | Project |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| 관리 노드 | AdministrationNode | 1 | Any | controlPointCap, efficiency, leoOnlyCpCap, powerConsumer, upkeep | -10 | 40 | 0 | 4 |  | Money:10.333333, Boost:1, Water:1.166667, Volatiles:1.196667, Metals:0.03, NobleMetals:0.03 | Project_AdministrationNode |
| 자동화된 핵분열 원자로 | AutomatedFissionPile | 1 | Any | powerProducer, upkeep | 20 | 0 | 0 | 0 |  | Water:0.5, Fissiles:0.05 | Project_AutomatedFissionPile |
| 자동화된 태양광 수집기 | AutomatedSolarCollector | 1 | Any | powerProducer | 20 | 0 | 0 | 0 |  |  | Project_AutomatedSolarCollector |
| 자동화된 보급창 | AutomatedSupplyDepot | 1 | Any | powerConsumer, resupply | -3 | 0 | 0 | 0 |  |  | Project_AutomatedSupplyDepot |
| 방송국 | BroadcastOutlet | 1 | Any | economy, powerConsumer, upkeep | -5 | 5 | 0 | 0 | Money:1, Influence:4 | Money:4.041667, Water:0.145833, Volatiles:0.145833 | Project_BroadcastOutlet |
| 건설 모듈 | ConstructionModule | 1 | Any | powerConsumer, upkeep | -10 | 6 | 0 | 0 |  | Money:3.05, Water:1.175, Volatiles:1.175, Metals:3, NobleMetals:0.25 | Project_ConstructionModule |
| 에너지 연구실 | EnergyLab | 1 | Any | powerConsumer, research, upkeep | -10 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:1.0875, Fissiles:0.001 | Project_EnergyLab |
| 핵분열 원자로 | FissionPile | 1 | Any | powerProducer, upkeep | 20 | 4 | 0 | 0 |  | Money:2.033333, Water:0.616667, Volatiles:0.366667, Fissiles:0.05 | Project_FissionPile |
| 핵융합 원자로 | FusionPile | 1 | Any | powerProducer, upkeep | 40 | 5 | 0 | 0 |  | Money:3.041667, Water:1.145833, Volatiles:0.645833, Fissiles:0.02 | Project_FusionPile |
| 고출력 핵분열 원자로 | HeavyFissionPile | 1 | Any | powerProducer, upkeep | 30 | 4 | 0 | 0 |  | Money:3.033333, Water:0.616667, Volatiles:0.366667, Fissiles:0.075 | Project_HeavyFissionPile |
| 고출력 핵융합 원자로 | HeavyFusionPile | 1 | Any | powerProducer, upkeep | 70 | 10 | 0 | 0 |  | Money:5.083333, Water:1.291667, Volatiles:0.791667, Metals:0.1, NobleMetals:0.1, Fissiles:0.02 | Project_HeavyFusionPile |
| 수경재배실 | HydroponicsBay | 1 | Any | farm, powerConsumer, upkeep | -10 | 1 | 0 | 0 |  | Money:0.008333, Water:0.029167, Volatiles:0.029167 | Project_HydroponicsBay |
| 정보 과학 연구실 | InformationScienceLab | 1 | Any | powerConsumer, research, upkeep | -10 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_InformationScienceLab |
| 생명 과학 연구실 | LifeScienceLab | 1 | Any | powerConsumer, research, upkeep | -5 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.5875, Volatiles:0.5875 | Project_LifeScienceLab |
| 해병 소대 병영 | MarinePlatoonBarracks | 1 | Any | economy, powerConsumer, upkeep | -5 | 30 | 0 | 0 | Operations:2 | Money:3.25, Water:0.875, Volatiles:1.875, Metals:1, NobleMetals:0.1 | Project_MarinePlatoonBarracks |
| 재료 연구실 | MaterialsLab | 1 | Any | powerConsumer, research, upkeep | -6 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875, Metals:0.1, NobleMetals:0.1 | Project_MaterialsLab |
| 군사 과학 연구실 | MilitaryScienceLab | 1 | Any | powerConsumer, research, upkeep | -5 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_MilitaryScienceLab |
| 거점 방어 배열 | PointDefenseArray | 1 | Any | powerConsumer, upkeep | -10 | 3 | 0 | 0 |  | Money:2.025, Water:0.0875, Volatiles:0.1875, Metals:0.1 | Project_PointDefenseArray |
| 주둔지 | Quarters | 1 | Any | economy, powerConsumer, upkeep | -2 | 50 | 0 | 0 | Money:3, Influence:2 | Water:1.558333, Volatiles:1.558333 | Project_Quarters |
| 사회 과학 연구실 | SocialScienceLab | 1 | Any | powerConsumer, research, upkeep | -4 | 3 | 0 | 0 | Research:5 | Money:3.025, Water:0.0875, Volatiles:0.0875 | Project_SocialScienceLab |
| 태양광 수집기 | SolarCollector | 1 | Any | powerProducer, upkeep | 20 | 1 | 0 | 0 |  | Money:1.008333, Water:0.029167, Volatiles:0.029167 | Project_SolarCollector |
| 우주 정거장 | SpaceDock | 1 | Any | powerConsumer, resupply, shipyard, upkeep | -20 | 40 | 0 | 0 |  | Money:0.333333, Water:1.166667, Volatiles:1.166667, Metals:1, NobleMetals:0.1 | Project_SpaceDock |
| 우주 과학 연구실 | SpaceScienceLab | 1 | Any | powerConsumer, research, upkeep | -5 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_SpaceScienceLab |
| 보급창 | SupplyDepot | 1 | Any | resupply, upkeep | 0 | 3 | 0 | 0 |  | Money:0.025, Water:0.0875, Volatiles:0.0875 | Project_SupplyDepot |
| 외계학 연구실 | XenologyLab | 1 | Any | powerConsumer, research, upkeep | -10 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_XenologyLab |
| 자동화된 채굴단지 | AutomatedMiningComplex | 1 | Base | mine, powerConsumer, upkeep | -12 | 0 | 0 | 0 |  | Water:2, Volatiles:0.5 | Project_AutomatedMiningComplex |
| 자동화된 전초기지 코어 | AutomatedOutpostCore | 1 | Base | core, mcConsumer | 0 | 0 | -1 | 0 | MissionControl:-1 |  | Project_AutomatedOutpostCore |
| 전초기지 코어 | OutpostCore | 1 | Base | core, mcConsumer, upkeep | 0 | 5 | -2 | 0 | MissionControl:-2 | Money:3.041667, Water:0.145833, Volatiles:0.145833 | Project_OutpostCore |
| 전초기지 채굴단지 | OutpostMiningComplex | 1 | Base | mine, powerConsumer, upkeep | -10 | 12 | 0 | 0 |  | Money:6.1, Water:2.35, Volatiles:0.85 | Project_OutpostMiningComplex |
| 반물질 포획기 | AntimatterTrap | 1 | Station | powerConsumer, research, upkeep | -5 | 2 | 0 | 0 | Research:5 | Money:2.016667, Water:0.058333, Volatiles:0.058333, Metals:0.1, NobleMetals:0.03 | Project_AntimatterTrap |
| 자동화된 플랫폼 코어 | AutomatedPlatformCore | 1 | Station | core, mcConsumer | 0 | 0 | -1 | 0 | MissionControl:-1 |  | Project_AutomatedPlatformCore |
| 자동화된 태양 반사경 | AutomatedSolarMirror | 1 | Station | powerConsumer, upkeep | -1 | 0 | 0 | 0 |  | Money:1, Metals:0.1, NobleMetals:0.03 | Project_AutomatedSolarMirror |
| 기후 연구실 | ClimateLab | 1 | Station | powerConsumer, research, upkeep | -5 | 3 | 0 | 0 | Research:5 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_ClimateLab |
| 감청 초소 | ListeningPost | 1 | Station | economy, powerConsumer, upkeep | -10 | 8 | 0 | 0 | Operations:1 | Money:5.066667, Water:0.233333, Volatiles:0.233333 | Project_ListeningPost |
| 입자 충돌기 | ParticleCollider | 1 | Station | powerConsumer, research, upkeep | -100 | 10 | 0 | 0 | Research:2, Antimatter:0.0001 | Money:6.083333, Water:2.291667, Volatiles:2.291667, Metals:1, NobleMetals:1, Fissiles:1 | Project_ParticleCollider |
| 플랫폼 코어 | PlatformCore | 1 | Station | core, mcConsumer, upkeep | 0 | 3 | -2 | 0 | MissionControl:-2 | Money:2.025, Water:0.0875, Volatiles:0.0875 | Project_PlatformCore |
| 태양 반사경 | SolarMirror | 1 | Station | powerConsumer, upkeep | -1 | 1 | 0 | 0 |  | Money:1.008333, Water:0.029167, Volatiles:0.029167, Metals:0.1, NobleMetals:0.03 | Project_SolarMirror |
| 관광객 침실 | TouristBerth | 1 | Station | economy, powerConsumer, upkeep | -3 | 2 | 0 | 0 | Money:20 | Money:0.016667, Boost:0.2, Water:0.058333, Volatiles:0.058333 | Project_TouristBerth |
| 관리 타워 | AdministrationTower | 2 | Any | controlPointCap, efficiency, leoOnlyCpCap, mcProducer, powerConsumer, upkeep | -40 | 200 | 1 | 12 | MissionControl:1 | Money:31.666667, Boost:4, Water:5.833333, Volatiles:5.933333, Metals:0.1, NobleMetals:0.1 | Project_AdministrationTower |
| 중앙 통신 시설 | CommunicationsHub | 2 | Any | economy, powerConsumer, upkeep | -20 | 25 | 0 | 0 | Money:3, Influence:10 | Money:20.208333, Water:0.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_CommunicationsHub |
| 심우주 망원경 | DeepSpaceTelescope | 2 | Any | powerConsumer, research, upkeep | -20 | 15 | 0 | 0 | Research:5 | Money:3.125, Water:0.4375, Volatiles:0.4375 | Project_DeepSpaceTelescope |
| 에너지 연구 센터 | EnergyResearchCenter | 2 | Any | powerConsumer, research, upkeep | -40 | 20 | 0 | 0 | Research:10 | Money:6.166667, Water:0.583333, Volatiles:3.583333, Metals:0.1, NobleMetals:0.1, Fissiles:0.005 | Project_EnergyResearchCenter |
| 농장 | Farm | 2 | Any | farm, powerConsumer, upkeep | -40 | 5 | 0 | 0 |  | Money:0.041667, Water:0.145833, Volatiles:0.145833 | Project_Farm |
| 핵분열 반응로 배열 | FissionReactorArray | 2 | Any | powerProducer, upkeep | 85 | 20 | 0 | 0 |  | Money:6.166667, Water:2.583333, Volatiles:1.583333, Fissiles:0.2 | Project_FissionReactorArray |
| 핵융합 반응로 배열 | FusionReactorArray | 2 | Any | powerProducer, upkeep | 170 | 25 | 0 | 0 |  | Money:10.208333, Water:3.729167, Volatiles:2.729167, Fissiles:0.05 | Project_FusionReactorArray |
| 고출력 핵분열 반응로 배열 | HeavyFissionReactorArray | 2 | Any | powerProducer, upkeep | 128 | 20 | 0 | 0 |  | Money:8.166667, Water:2.583333, Volatiles:1.583333, Fissiles:0.3 | Project_HeavyFissionReactorArray |
| 고출력 핵융합 반응로 배열 | HeavyFusionReactorArray | 2 | Any | powerProducer, upkeep | 300 | 50 | 0 | 0 |  | Money:12.416667, Water:4.458333, Volatiles:3.458333, Metals:0.5, NobleMetals:0.5, Fissiles:0.08 | Project_HeavyFusionReactorArray |
| 정보 과학 연구 센터 | InformationScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -40 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:1.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_InformationScienceResearchCenter |
| 적층 방어 배열 | LayeredDefenseArray | 2 | Any | powerConsumer, upkeep | -40 | 15 | 0 | 0 |  | Money:10.125, Water:0.4375, Volatiles:1.4375, Metals:1, NobleMetals:0.5 | Project_LayeredDefenseArray |
| 생명 과학 연구 센터 | LifeScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -20 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:1.729167, Volatiles:1.729167 | Project_LifeScienceResearchCenter |
| 해병 중대 병영 | MarineCompanyBarracks | 2 | Any | economy, powerConsumer, upkeep | -20 | 150 | 0 | 0 | Operations:6 | Money:11.25, Water:4.375, Volatiles:6.375, Metals:2, NobleMetals:0.2 | Project_MarineCompanyBarracks |
| 재료 연구 센터 | MaterialsResearchCenter | 2 | Any | powerConsumer, research, upkeep | -24 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:1.729167, Volatiles:1.729167, Metals:1, NobleMetals:0.5 | Project_MaterialsResearchCenter |
| 군사 과학 연구 센터 | MilitaryScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -20 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:0.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_MilitaryScienceResearchCenter |
| 나노 공장 | Nanofactory | 2 | Any | economy, powerConsumer, upkeep | -40 | 30 | 0 | 0 | Money:90 | Money:10.25, Water:3.875, Volatiles:3.875, Metals:10, NobleMetals:1 | Project_Nanofactory |
| 관제소 | OperationsCenter | 2 | Any | mcProducer, powerConsumer, upkeep | -100 | 200 | 4 | 0 | MissionControl:4 | Money:31.666667, Water:5.833333, Volatiles:10.833333, Metals:5, NobleMetals:2.5 | Project_OperationsCenter |
| 의료 센터 | OrbitalHospital | 2 | Any | economy, powerConsumer, upkeep | -30 | 120 | 0 | 0 | Money:90 | Money:1, Boost:1, Water:8.5, Volatiles:6.5 | Project_OrbitalHospital |
| 연구 캠퍼스 | ResearchCampus | 2 | Any | mcConsumer, powerConsumer, research, upkeep | -50 | 200 | -1 | 0 | Research:60, MissionControl:-1 | Money:31.666667, Water:8.833333, Volatiles:8.833333 | Project_ResearchCampus |
| 주거 모듈 | ResidentialModule | 2 | Any | economy, powerConsumer, upkeep | -15 | 500 | 0 | 0 | Money:12, Influence:6 | Boost:0.5, Water:17.583333, Volatiles:15.583333, Metals:1 | Project_ResidentialModule |
| 조선소 | Shipyard | 2 | Any | powerConsumer, resupply, shipyard, upkeep | -80 | 120 | 0 | 0 |  | Money:1, Water:3.5, Volatiles:3.5, Metals:3, NobleMetals:0.5 | Project_Shipyard |
| 스컹크웍스 | SkunkWorks | 2 | Any | powerConsumer, research, upkeep | -30 | 50 | 0 | 0 | Projects:1 | Money:10.416667, Water:1.458333, Volatiles:4.458333, Metals:3, NobleMetals:0.3 | Project_SkunkWorks |
| 사회과학 연구 센터 | SocialScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -16 | 25 | 0 | 0 | Research:10 | Money:8.208333, Water:0.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_SocialScienceResearchCenter |
| 태양광 발전 배열 | SolarArray | 2 | Any | powerProducer, upkeep | 80 | 5 | 0 | 0 |  | Money:3.041667, Water:0.145833, Volatiles:0.145833 | Project_SolarArray |
| 우주 과학 연구 센터 | SpaceScienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -20 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:0.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_SpaceScienceResearchCenter |
| 외계 과학 연구 센터 | XenoscienceResearchCenter | 2 | Any | powerConsumer, research, upkeep | -40 | 25 | 0 | 0 | Research:10 | Money:6.208333, Water:0.729167, Volatiles:0.829167, Metals:0.1, NobleMetals:0.1 | Project_XenoscienceResearchCenter |
| 정착지 코어 | SettlementCore | 2 | Base | core, mcConsumer, upkeep | 0 | 25 | -3 | 0 | MissionControl:-3 | Money:10.208333, Water:0.729167, Volatiles:0.729167 | Project_SettlementCore |
| 정착지 채굴단지 | SettlementMiningComplex | 2 | Base | mine, powerConsumer, upkeep | -40 | 60 | 0 | 0 |  | Money:30.5, Water:6.75, Volatiles:3.75 | Project_SettlementMiningComplex |
| 반물질 수확기 | AntimatterHarvester | 2 | Station | powerConsumer, research, upkeep | -20 | 10 | 0 | 0 | Research:10 | Money:5.083333, Water:0.291667, Volatiles:0.291667, Metals:0.5, NobleMetals:0.1 | Project_AntimatterHarvester |
| 원자파괴장치 | Atomsmasher | 2 | Station | powerConsumer, research, upkeep | -250 | 20 | 0 | 0 | Research:5, Antimatter:0.01 | Money:20.166667, Water:10.583333, Volatiles:10.583333, Metals:5, NobleMetals:5, Fissiles:3 | Project_Atomsmasher |
| 기후 연구 센터 | ClimateResearchCenter | 2 | Station | powerConsumer, research, upkeep | -20 | 15 | 0 | 0 | Research:10 | Money:6.125, Water:0.4375, Volatiles:0.5375, Metals:0.1, NobleMetals:0.1 | Project_ClimateResearchCenter |
| 궤도 거주지 코어 | OrbitalCore | 2 | Station | core, mcConsumer, upkeep | 0 | 15 | -3 | 0 | MissionControl:-3 | Money:10.125, Water:0.4375, Volatiles:0.4375 | Project_OrbitalCore |
| 정찰 어레이 | ReconnaissanceArray | 2 | Station | economy, powerConsumer, upkeep | -40 | 40 | 0 | 0 | Operations:2 | Money:15.333333, Water:1.166667, Volatiles:2.166667, Metals:1, NobleMetals:0.1 | Project_ReconnaissanceArray |
| 태양 반사경 배열 | SolarMirrorArray | 2 | Station | powerConsumer, upkeep | -4 | 5 | 0 | 0 |  | Money:5.041667, Water:0.145833, Volatiles:0.145833, Metals:1, NobleMetals:0.1 | Project_SolarMirrorArray |
| 우주 호텔 | SpaceHotel | 2 | Station | economy, powerConsumer, upkeep | -30 | 200 | 0 | 0 | Money:120, Influence:2 | Money:1.666667, Boost:3, Water:8.833333, Volatiles:7.833333 | Project_SpaceHotel |
| 관리 복합단지 | AdministrationComplex | 3 | Any | controlPointCap, efficiency, leoOnlyCpCap, mcProducer, powerConsumer, upkeep | -160 | 1000 | 2 | 30 | MissionControl:2 | Money:98.333333, Boost:12, Water:29.166667, Volatiles:29.666667, Metals:0.5, NobleMetals:0.5 | Project_AdministrationComplex |
| 농업 복합단지 | AgricultureComplex | 3 | Any | farm, powerConsumer, upkeep | -120 | 25 | 0 | 0 |  | Money:0.208333, Water:0.729167, Volatiles:0.729167 | Project_AgricultureComplex |
| 전투 기지 | Battlestations | 3 | Any | powerConsumer, upkeep | -240 | 75 | 0 | 0 |  | Money:30.625, Water:2.1875, Volatiles:5.1875, Metals:3, NobleMetals:1 | Project_Battlestations |
| 민간 복합단지 | CivilianComplex | 3 | Any | economy, powerConsumer, upkeep | -120 | 2500 | 0 | 0 | Money:40, Influence:10 | Boost:1, Water:82.916667, Volatiles:78.916667, Metals:2 | Project_CivilianComplex |
| 지휘 센터 | CommandCenter | 3 | Any | mcProducer, powerConsumer, upkeep | -300 | 1000 | 10 | 0 | MissionControl:10 | Money:108.333333, Water:29.166667, Volatiles:39.166667, Metals:10, NobleMetals:5 | Project_CommandCenter |
| 에너지 연구원 | EnergyInstitute | 3 | Any | powerConsumer, research, upkeep | -120 | 100 | 0 | 0 | Research:15 | Money:18.833333, Water:2.916667, Volatiles:12.916667, Metals:0.5, NobleMetals:0.5, Fissiles:0.01 | Project_EnergyInstitute |
| 핵분열 반응로 농장 | FissionReactorFarm | 3 | Any | powerProducer, upkeep | 250 | 100 | 0 | 0 |  | Money:18.833333, Water:8.916667, Volatiles:5.916667, Fissiles:0.5 | Project_FissionReactorFarm |
| 주조소 | Foundry | 3 | Any | powerConsumer, research, upkeep | -90 | 250 | 0 | 0 | Projects:2 | Money:32.083333, Water:7.291667, Volatiles:17.291667, Metals:10, NobleMetals:1 | Project_Foundry |
| 핵융합 반응로 농장 | FusionReactorFarm | 3 | Any | powerProducer, upkeep | 500 | 125 | 0 | 0 |  | Money:31.041667, Water:13.645833, Volatiles:9.645833, Fissiles:0.1 | Project_FusionReactorFarm |
| 우주 병원 | GeriatricsFacility | 3 | Any | economy, powerConsumer, upkeep | -90 | 600 | 0 | 0 | Money:300 | Money:5, Boost:3, Water:32.5, Volatiles:27.5 | Project_GeriatricsFacility |
| 고출력 핵분열 반응로 농장 | HeavyFissionReactorFarm | 3 | Any | powerProducer, upkeep | 375 | 100 | 0 | 0 |  | Money:24.833333, Water:8.916667, Volatiles:5.916667, Fissiles:0.75 | Project_HeavyFissionReactorFarm |
| 고출력 핵융합 반응로 농장 | HeavyFusionReactorFarm | 3 | Any | powerProducer, upkeep | 900 | 150 | 0 | 0 |  | Money:37.25, Water:14.375, Volatiles:10.375, Metals:1, NobleMetals:1, Fissiles:0.2 | Project_HeavyFusionReactorFarm |
| 정보 과학 연구원 | InformationScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -120 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:6.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_InformationScienceInstitute |
| 생명 과학 연구원 | LifeScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -60 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:6.645833, Volatiles:6.645833 | Project_LifeScienceInstitute |
| 해병 대대 병영 | MarineBattalionBarracks | 3 | Any | economy, powerConsumer, upkeep | -60 | 750 | 0 | 0 | Operations:12 | Money:36.25, Water:21.875, Volatiles:24.875, Metals:3, NobleMetals:0.3 | Project_MarineBattalionBarracks |
| 재료 연구원 | MaterialsInstitute | 3 | Any | powerConsumer, research, upkeep | -72 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:6.645833, Volatiles:6.645833, Metals:3, NobleMetals:1.5 | Project_MaterialsInstitute |
| 미디어 센터 | MediaCenter | 3 | Any | economy, powerConsumer, upkeep | -60 | 125 | 0 | 0 | Money:10, Influence:25 | Money:101.041667, Water:3.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_MediaCenter |
| 군사 과학 연구원 | MilitaryScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -60 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:3.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_MilitaryScienceInstitute |
| 나노 제조 복합단지 | NanofacturingComplex | 3 | Any | economy, powerConsumer, upkeep | -120 | 150 | 0 | 0 | Money:300 | Money:21.25, Water:14.375, Volatiles:14.375, Metals:30, NobleMetals:3 | Project_NanofacturingComplex |
| 연구 대학 | ResearchUniversity | 3 | Any | mcConsumer, powerConsumer, research, upkeep | -150 | 1000 | -2 | 0 | Research:200, MissionControl:-2 | Money:108.333333, Water:39.166667, Volatiles:39.166667 | Project_ResearchUniversity |
| 사회 과학 연구원 | SocialScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -48 | 125 | 0 | 0 | Research:15 | Money:25.041667, Water:3.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_SocialScienceInstitute |
| 태양광 농장 | SolarFarm | 3 | Any | powerProducer, upkeep | 240 | 25 | 0 | 0 |  | Money:5.208333, Water:0.729167, Volatiles:0.729167 | Project_SolarFarm |
| 우주 과학 연구원 | SpaceScienceInstitute | 3 | Any | powerConsumer, research, upkeep | -60 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:3.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_SpaceScienceInstitute |
| 스페이스웍스 | Spaceworks | 3 | Any | powerConsumer, resupply, shipyard, upkeep | -240 | 400 | 0 | 0 |  | Money:3.333333, Water:11.666667, Volatiles:11.666667, Metals:10, NobleMetals:1 | Project_Spaceworks |
| 외계 과학 연구원 | XenoscienceInstitute | 3 | Any | powerConsumer, research, upkeep | -120 | 125 | 0 | 0 | Research:15 | Money:19.041667, Water:3.645833, Volatiles:4.145833, Metals:0.5, NobleMetals:0.5 | Project_XenoscienceInstitute |
| 식민지 코어 | ColonyCore | 3 | Base | core, mcConsumer, upkeep | 0 | 125 | -4 | 0 | MissionControl:-4 | Money:21.041667, Water:3.645833, Volatiles:3.645833 | Project_ColonyCore |
| 식민지 채굴단지 | ColonyMiningComplex | 3 | Base | mine, powerConsumer, upkeep | -200 | 200 | 0 | 0 |  | Money:61.666667, Water:20.833333, Volatiles:11.833333 | Project_ColonyMiningComplex |
| 반물질 농장 | AntimatterFarm | 3 | Station | powerConsumer, research, upkeep | -80 | 50 | 0 | 0 | Research:15 | Money:10.416667, Water:1.458333, Volatiles:1.458333, Metals:1.5, NobleMetals:1 | Project_AntimatterFarm |
| 아르고스 복합단지 | ArgusComplex | 3 | Station | economy, powerConsumer, upkeep | -120 | 200 | 0 | 0 | Operations:3 | Money:31.666667, Water:5.833333, Volatiles:8.833333, Metals:3, NobleMetals:0.3 | Project_ArgusComplex |
| 기후 연구원 | ClimateInstitute | 3 | Station | powerConsumer, research, upkeep | -60 | 75 | 0 | 0 | Research:15 | Money:20.625, Water:2.1875, Volatiles:2.6875, Metals:0.5, NobleMetals:0.5 | Project_ClimateInstitute |
| 헬륨-3 광산 | Helium-3Mine | 3 | Station | mcConsumer, powerConsumer, upkeep | -300 | 75 | -3 | 0 | MissionControl:-3 | Money:30.625, Water:4.1875, Volatiles:4.1875, Metals:10, NobleMetals:1.5 | Project_Helium-3Mine |
| 성간 발사 시설 | InterstellarLaunchingLaser | 3 | Station | mcConsumer, powerConsumer, upkeep | -5000 | 80 | -20 | 0 | MissionControl:-20 | Money:20.666667, Water:2.333333, Volatiles:2.333333 | Project_InterstellarLaunchingLaser |
| 링형 거주지 코어 | RingCore | 3 | Station | core, mcConsumer, upkeep | 0 | 75 | -4 | 0 | MissionControl:-4 | Money:20.625, Water:2.1875, Volatiles:2.1875 | Project_RingCore |
| 센티넬 복합단지 | SentinelComplex | 3 | Station | mcConsumer, powerConsumer, upkeep | -150 | 100 | -1 | 0 | MissionControl:-1 | Money:20.833333, Water:2.916667, Volatiles:2.916667 | Project_SentinelComplex |
| 솔레타 | Soletta | 3 | Station | powerConsumer, upkeep | -12 | 25 | 0 | 0 |  | Money:10.208333, Water:0.729167, Volatiles:0.729167, Metals:3, NobleMetals:0.5 | Project_Soletta |
| 우주 리조트 | SpaceResort | 3 | Station | economy, powerConsumer, upkeep | -90 | 1000 | 0 | 0 | Money:400, Influence:5 | Money:8.333333, Boost:6, Water:39.166667, Volatiles:34.166667 | Project_SpaceResort |
| 초대형 입자 가속기 | Supercollider | 3 | Station | powerConsumer, research, upkeep | -750 | 100 | 0 | 0 | Research:10, Antimatter:0.1 | Money:120.833333, Water:32.916667, Volatiles:32.916667, Metals:20, NobleMetals:20, Fissiles:10 | Project_Supercollider |
