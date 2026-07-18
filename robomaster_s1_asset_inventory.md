# RoboMaster S1 Asset Inventory

This document lists the RoboMaster Windows app assets that appear to contain
RoboMaster S1 model data and audio data. The investigation was limited to file
metadata, container headers, file sizes, and embedded asset-name strings. No
asset extraction or export was performed.

## Scope

- Application data folder:
  `C:\Program Files\DJI Product\RoboMaster\RoboMaster_Data`
- Target asset types:
  - RoboMaster S1 3D model / mesh / material / texture candidates
  - AudioClip / sound effect / music candidates
  - UI/web resource audio that exists as standalone files
- Unity asset tooling reference:
  AssetStudio can inspect Unity `assets`, `resS`, `resource`, and bundle data,
  including Mesh, Texture2D, Animator, AnimationClip, and AudioClip entries.

## Top-Level Unity Containers

| File | Size | Header / role | Notes |
|---|---:|---|---|
| `resources.assets.resS` | 295,419,464 | external serialized resource data | Largest external data store. Likely contains large texture/mesh/audio binary payloads referenced by `resources.assets`. |
| `resources.assets` | 133,489,648 | Unity serialized asset metadata/data | Main asset table. Contains S1 material names, model hierarchy names, AudioClip names, UI textures, and animation names. |
| `resources.resource` | 59,081,936 | `FSB5` | Audio bank body. Stores encoded audio data referenced by Unity AudioClip metadata. |
| `level3.resS` | 15,805,788 | external scene data | External data for `level3`. |
| `level3` | 2,899,844 | Unity scene/level data | Contains the clearest detailed S1 physical-part mesh names. |
| `sharedassets7.assets.resS` | 12,234,080 | external shared data | Shared scene data, likely lightmaps/textures for virtual robot scenes. |
| `sharedassets3.assets.resS` | 8,913,696 | external shared data | Shared scene data, likely lightmaps/textures. |
| `sharedassets10.assets` | 3,884,924 | shared asset metadata | Terrain/detail shader/material references; not primary S1 model. |
| `globalgamemanagers` | 2,958,456 | Unity manager metadata | Contains scene references, script class names, resource paths, and AudioClip path strings. |

## Most Detailed RoboMaster S1 Model Candidate

The highest-confidence detailed RoboMaster S1 model candidate is:

| Priority | Container set | Reason |
|---:|---|---|
| 1 | `level3` + `level3.resS` | Contains direct physical-part names for the S1, including chassis, gimbal, wheel, armor, gun, magazine, and LED parts. This is more detailed and more physical-part-specific than the virtual robot scenes. |
| 2 | `resources.assets` + `resources.assets.resS` | Contains materials, textures, animations, hierarchy paths, and model-related names used by the detailed S1 model. This is the main companion asset table for visible detail. |
| 3 | `level5`, `level7`, `level10` | Contains `VirtualRobot`, `Wheel_FL`, `Wheel_FR`, `ArmorFrontLED`, etc. These appear to be simplified virtual/scene robot representations rather than the most detailed physical S1 model. |

### Detailed Model Names Found In `level3`

The following embedded names indicate that `level3` contains the detailed S1
model hierarchy:

| Category | Names |
|---|---|
| Chassis | `chassis`, `Chassis_down`, `Chassis_down_down`, `Chassis_Top`, `Gimbal Base` |
| Gimbal | `Gimbal`, `guntop`, `Yuntai armor plate_L`, `Yuntai armor plate_R` |
| Gun | `Water Bullet Gun`, `Water Bullet Gun LED`, `Gun Magazine`, `sound_low` |
| Wheels | `Mecanum Wheel_01`, `Mecanum Wheel_02`, `Mecanum Wheel_03`, `Mecanum Wheel_04`, `Mecanum Wheel_01_inside`, `Mecanum Wheel_02_inside`, `Mecanum Wheel_03_inside`, `Mecanum Wheel_04_inside` |
| Tire sleeves | `Wheel Rubber Sleeve_01`, `Wheel Rubber Sleeve_02`, `Wheel Rubber Sleeve_03`, `Wheel Rubber Sleeve_04` |
| Armor | `Armor Module_F`, `Armor Module_B`, `Armor Module_L`, `Armor Module_R`, `Armor Module_F_inside`, `Armor Module_B_inside`, `ArmorModule_L_inside`, `Armor Module_R_inside` |
| Armor wiring/lines | `line_Armor Module_F`, `line_Armor Module_B`, `line_Armor Module_L`, `line_Armor Module_R` |

### Companion Material / Texture Names Found In `resources.assets`

`resources.assets` contains many material and texture names that correspond to
the physical S1 model:

| Category | Example names |
|---|---|
| Robot materials | `mat_robot_1`, `mat_robot_2`, `mat_robot_3`, `mat_robot_4`, `mat_robot_5`, `mat_robot_led` |
| Gun materials/textures | `GUN_Base_Color`, `GUN_Normal_OpenGL`, `GUN_Metallic`, `GUN_Roughness`, `GUN_Mixed_AO`, `GUN_Height`, `gun_UV_E` |
| Armor materials/textures | `ArmorModule_Base_Color`, `ArmorModule_Base_Color_UV_E`, `ArmorModule_Normal_OpenGL`, `ArmorModule_Metallic`, `ArmorModule_Roughness`, `ArmorModule_Mixed_AO`, `ArmorModule_inside_UV_E` |
| Armor plates | `ArmorPlate_01`, `ArmorPlate_02`, `ArmorPlate_03`, `ArmorPlate_04`, `ArmorPlate_05`, `ArmorPlate_06` |
| Hierarchy paths | `Gimbal/guntop/Water Bullet Gun`, `Gimbal/Water Bullet Gun LED/yuntailight_01` ... `yuntailight_08`, `Gimbal Base/chassis/Armor Module_*` |

## Virtual Robot / Scene Model Candidates

`level5`, `level7`, and `level10` contain similar virtual robot scene names:

| Container | Example names | Interpretation |
|---|---|---|
| `level5` | `VirtualRobot`, `VirtualRobotEnemy`, `TargetRobot`, `Wheel_FL`, `Wheel_FR`, `Wheel_BL`, `Wheel_BR`, `Gimbal`, `ArmorFrontLED`, `ArmorBackLED`, `ArmorLeftLED`, `ArmorRightLED` | Virtual game/training robot representation. |
| `level7` | `VirtualRobot`, `Model`, `Wheel_Main`, `Wheels`, `Gun`, `Sound`, `Fire`, `Shockwave` | Virtual robot/effect scene. |
| `level10` | `VirtualRobot`, `Model`, `Wheel_Main`, `Wheels`, `Gun`, `Sound`, `Fire`, `Shockwave` | Virtual robot/effect scene. |

These are useful for game/visualization effects, but they are not the best
candidate for the most detailed physical S1 model.

## Audio Data Locations

### Main Audio Bank

| File | Evidence | Role |
|---|---|---|
| `resources.resource` | Starts with `FSB5` | Main encoded audio bank. This is the primary binary location for app sound effects, voice prompts, and music. |
| `resources.assets` | Contains AudioClip-style names such as `sfx_*`, `music_*`, `audio_00000` ... `audio_00027` | Audio metadata and clip names. |
| `globalgamemanagers` | Contains resource paths such as `audios/...`, `audio/...`, `ac/...` | Resource path index / manager metadata. |

### AudioClip / Sound Names Found

Important audio names found in `resources.assets`:

| Group | Names |
|---|---|
| Common UI / operation | `sfx_ui_click`, `sfx_ui_click_importent`, `sfx_common_toast`, `sfx_common_window_popup`, `sfx_success`, `sfx_failure`, `sfx_block_click`, `sfx_block_delete` |
| Recording / camera | `common_record_start`, `common_record_end`, `common_takephoto` |
| Solo challenge | `music_solo_challenge`, `sfx_solo_challenge_finish`, `sfx_solo_challenge_hit`, `sfx_solo_challenge_levelup`, `sfx_solo_challenge_markAimed`, `sfx_solo_challenge_speedup`, `sfx_solo_challenge_success` |
| Battle | `music_battle_freeforall_final30s`, `music_battle_freeforall_room`, `music_battle_leaderboard`, `music_battle_racing_gaming`, `music_battle_racing_room`, `sfx_battle_countdown_123`, `sfx_battle_countdown_start`, `sfx_battle_death`, `sfx_battle_get_marker`, `sfx_battle_hit_sucess`, `sfx_battle_kill_sucess`, `sfx_battle_lastcheckpoint`, `sfx_battle_lose`, `sfx_battle_revive`, `sfx_battle_win` |
| Gun / cooldown | `sfx_shoot_CoolDown` |
| Auto follow | `sfx_AutoFollow_Open`, `sfx_AutoFollow_Search`, `sfx_AutoFollow_Lock`, `sfx_AutoFollow_Following` |
| Piano | `sfx_piano_100` through `sfx_piano_135` |
| Generic numbered clips | `audio_00000` through `audio_00027` |

Important resource paths found in `globalgamemanagers`:

| Group | Example paths |
|---|---|
| Country/region voice or acoustic resources | `ac/ad_w`, `ac/ae_w`, ..., `ac/jp_w`, ..., `ac/us_w` |
| Auto follow | `audio/sfx_autofollow_following`, `audio/sfx_autofollow_lock`, `audio/sfx_autofollow_open`, `audio/sfx_autofollow_search` |
| Code show | `audio/sfx_codeshow` |
| Common | `audios/common_record_start`, `audios/common_record_end`, `audios/common_takephoto` |
| Battle music | `audios/music/music_battle_freeforall_final30s`, `audios/music/music_battle_freeforall_room`, `audios/music/music_battle_leaderboard`, `audios/music/music_battle_racing_gaming`, `audios/music/music_battle_racing_room` |
| Solo music | `audios/music_solo_challenge` |
| Piano | `audios/piano/sfx_piano_100` through `audios/piano/sfx_piano_135` |

### Standalone Web/UI Audio

The only standalone audio files found by extension are Blockly/web UI sounds:

| File | Role |
|---|---|
| `StreamingAssets\visual_programming\static\blockly\media\click.mp3` |
| `StreamingAssets\visual_programming\static\blockly\media\click.ogg` |
| `StreamingAssets\visual_programming\static\blockly\media\click.wav` |
| `StreamingAssets\visual_programming\static\blockly\media\delete.mp3` |
| `StreamingAssets\visual_programming\static\blockly\media\delete.ogg` |
| `StreamingAssets\visual_programming\static\blockly\media\delete.wav` |
| `StreamingAssets\visual_programming\static\blockly\media\disconnect.mp3` |
| `StreamingAssets\visual_programming\static\blockly\media\disconnect.ogg` |
| `StreamingAssets\visual_programming\static\blockly\media\disconnect.wav` |

These are not the main RoboMaster S1 operation sounds. Main app sounds are in
the Unity audio bank described above.

## StreamingAssets

`StreamingAssets` mainly contains web/Blockly resources:

| Resource type | Examples |
|---|---|
| Visual programming UI | `visual_programming\static\js\*.js`, `visual_programming\static\css\*.css`, Blockly media |
| UI images | `RemoteControl.png`, `run_mode_1.gif`, `run_mode_2.gif`, `run_mode_3.gif`, `Signal_Level*.png`, `Wifi_Level*.png`, `underpan_Led8.png` |
| Text/config | `AppVerisonsCfg.txt`, `CopyIfNotExist.txt`, `webviewcopyfiles.txt`, country-code data |

This folder is important for Lab / visual-programming UI resources, but it is
not where the detailed S1 3D model or the main sound bank appears to live.

## Recommended Inspection Order In AssetStudio

For verification without guessing, load the folder
`C:\Program Files\DJI Product\RoboMaster\RoboMaster_Data` and inspect in this
order:

1. Filter by `Mesh` and inspect `level3` first.
2. Confirm that `level3` meshes match the physical part names listed above.
3. Filter by `Texture2D` and `Material`, then inspect `resources.assets`.
4. Filter by `AudioClip`, then inspect names from `resources.assets`.
5. Confirm that AudioClip payloads resolve through `resources.resource`.
6. Use `level5`, `level7`, and `level10` only if virtual/game robot scenes are needed.

## Summary

- Most detailed physical RoboMaster S1 model candidate:
  `level3` with companion data in `level3.resS`.
- Main detailed material/texture/hierarchy companion:
  `resources.assets` with large payloads in `resources.assets.resS`.
- Main audio metadata:
  `resources.assets` and path strings in `globalgamemanagers`.
- Main audio binary bank:
  `resources.resource` (`FSB5`).
- Standalone audio files:
  only Blockly/web UI sounds under `StreamingAssets`.

## Extracted FBX Folder Check

Additional inspection target:
`C:\Users\Tatsuya Ishikawa\Downloads\robomaster-s1-finchtest\New folder`

This folder contains exported FBX files and their companion textures. The check
used FBX size, companion texture count/size, and embedded part names.

### Highest-Detail Standard RoboMaster S1 FBX

| Rank | FBX | FBX size | Textures | Texture bytes | Result |
|---:|---|---:|---:|---:|---|
| 1 | `Time_robot\Time_robot.fbx` | 3,185,184 | 29 | 12,941,367 | Best standard S1 candidate. Contains chassis, gimbal, water gun, armor, mecanum wheels, tire sleeves, camera, Wi-Fi antenna, USB, and yuntai armor plate names, without the modified-machine indication seen in `ViewGuidance`. |
| 2 | `xw0607\xw0607.fbx` | 3,136,976 | 0 | 0 | Detailed standard S1 part names are present, but no companion textures in that folder. |
| 3 | `xw0607 (1)\xw0607.fbx` | 2,888,976 | 11 | 2,295,709 | Same standard S1 part-name coverage as `xw0607`, with companion textures. |
| 4 | `LAB 3 (1)\LAB 3.fbx` | 15,165,920 | 55 | 11,691,583 | Contains many standard S1 part names, but appears to be a lab/scene export rather than a clean robot-only model. |
| 5 | `EP_01A\EP_01A.fbx` | 3,687,856 | 46 | 22,956,473 | Large texture set, but embedded part-name coverage is weaker; gun-specific names such as `Water Bullet Gun` and `Gun Magazine` were not found in this FBX. |
| 6 | `VirtualRobot*`, `TargetRobot*`, `NetworkVirtualRobot*` | ~365,000-481,000 | 0 | 0 | Simplified virtual/game robot representations. Not the most detailed physical S1 model. |

### Excluded Modified / Non-Standard Candidate

`ViewGuidance\ViewGuidance.fbx` contains many S1 part names, but visual
inspection showed it is a modified/expanded machine rather than the standard
RoboMaster S1. It should not be used as the standard S1 reference model.

### Why `Time_robot` Is The Best Standard S1 Candidate

`Time_robot\Time_robot.fbx` has broad standard S1 part coverage and companion
textures:

| Category | Names found |
|---|---|
| Chassis | `chassis`, `Chassis_down`, `Chassis_Top`, `Gimbal Base` |
| Gimbal | `Gimbal`, `guntop`, `Yuntai armor plate_L`, `Yuntai armor plate_R` |
| Gun | `Water Bullet Gun`, `Water Bullet Gun LED`, `Gun Magazine` |
| Wheels | `Mecanum Wheel_01`, `Mecanum Wheel_02`, `Mecanum Wheel_03`, `Mecanum Wheel_04` |
| Tire sleeves | `Wheel Rubber Sleeve_01`, `Wheel Rubber Sleeve_02`, `Wheel Rubber Sleeve_03`, `Wheel Rubber Sleeve_04` |
| Armor | `Armor Module_F`, `Armor Module_B`, `Armor Module_L`, `Armor Module_R` |
| Small details | `Camera`, `WiFi Antenna`, `USB` |

### Large LAB Files

`LAB 3\LAB 3.fbx` and `LAB 3 (2)\LAB 3.fbx` are about 1.12 GB each and include
many textures. These are full lab/scene exports rather than the cleanest single
robot model. They may contain the robot plus environment geometry, but they are
not the best source when the target is the detailed robot itself.
