param(
    [string]$text,
    [int]$rate = 4
)
$rate = [Math]::Max(-10, [Math]::Min(10, $rate))
Add-Type -AssemblyName System.Speech
$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice.Rate = $rate
# 优先选中文语音
$zhVoice = $voice.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'zh-*' } | Select-Object -First 1
if ($zhVoice) { $voice.SelectVoice($zhVoice.VoiceInfo.Name) }
$voice.Speak($text)
