# RoboMaster S1 Sound Effects Notes

この文書は、RoboMaster S1 Wi-Fi通信で確認された効果音系DUSSを、制御・GUN種別切替仕様から分離して記録する。

## 1. 効果音候補DUSS

GUN初期化やモード切替付近で、以下のDUSSが送信される。

```text
PC -> S1
sender = 0x02
receiver = 0x01
attr = 0x40
cmdset/cmdid = 0x02/0x34
payload = 09 00 00 64 00
```

実機では、この送信タイミングで「シャキーン」という効果音が鳴ることがある。

## 2. 実装上の扱い

通常のGUN種別切替、LED GUN初期化、物理GUN初期化には、この効果音DUSSを含めない。

効果音を明示的に鳴らす機能を実装する場合のみ、ユーザー操作に紐付けて単独で送信する。

GUN種別切替時の「シャキーン」音を避けるため、通常の切替操作では以下のmode/skill遷移系DUSSも送信しない。

```text
0x3f/77 010301
0x3f/77 010401
0x3f/77 010201
0x3f/04 010301
0x3f/0a 0100
0x0a/a3 0000
```

GUN種別切替は `0x3f/09` のGUN設定blockと `0x3f/59` を中心に行う。

## 3. ACK

S1は同じ `cmdset/cmdid=0x02/0x34` に対してACKを返す。

```text
S1 -> PC
cmdset/cmdid = 0x02/0x34
payload = 00
```

## 4. 注意

`0x02/0x34 payload=0900006400` は、GUN種別をLED/物理に切り替えるための必須コマンドとして扱わない。
