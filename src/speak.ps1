param([string]$text)
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
# 语速加快 (默认 0，范围 -10 ~ 10)
$voice.Rate = 2
# 优先选中文语音
$zhVoice = $voice.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'zh-*' } | Select-Object -First 1
if ($zhVoice) { $voice.SelectVoice($zhVoice.VoiceInfo.Name) }
$voice.Speak($text)
