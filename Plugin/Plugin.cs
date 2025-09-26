using System.Linq;
using System.Reflection;
using System.Net.Http;
using System.Text;
using System.Threading.Tasks;
using BepInEx;
using BepInEx.Logging;
using HarmonyLib;

namespace SilksongCoyote;

[BepInPlugin(MyPluginInfo.PLUGIN_GUID, MyPluginInfo.PLUGIN_NAME, MyPluginInfo.PLUGIN_VERSION)]
public class Plugin : BaseUnityPlugin
{
    internal static new ManualLogSource Logger;
    private static readonly HttpClient httpClient = new HttpClient();
    private const string ServerUrl = "http://localhost:3329/";

    private void Awake()
    {
        // Plugin startup logic
        Logger = base.Logger;
        Logger.LogInfo($"Plugin {MyPluginInfo.PLUGIN_GUID} is loaded!");
        
        var h = new Harmony(MyPluginInfo.PLUGIN_GUID);
        h.PatchAll();
    }
    
    // HTTP utility method to send POST requests
    private static async Task SendHttpPostAsync(string eventName, object data = null)
    {
        try
        {
            object payload;
            if (data != null)
            {
                payload = new { @event = eventName, data = data };
            }
            else
            {
                payload = new { @event = eventName };
            }
            
            var json = Newtonsoft.Json.JsonConvert.SerializeObject(payload);
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            
            var response = await httpClient.PostAsync(ServerUrl, content);
            Logger.LogInfo($"HTTP POST sent for {eventName}: {response.StatusCode}");
        }
        catch (System.Exception ex)
        {
            Logger.LogError($"Failed to send HTTP POST for {eventName}: {ex.Message}");
        }
    }
    
    [HarmonyPatch(typeof(PlayerData))]
    static class PlayerData_TakeHealth_Patch
    {
        [HarmonyPatch(nameof(PlayerData.TakeHealth), new[] { typeof(int), typeof(bool), typeof(bool) })]
        [HarmonyPrefix]
        static void Prefix(int amount, bool hasBlueHealth, bool allowFracturedMaskBreak)
        {
            Plugin.Logger.LogInfo($"TakeHealth: {amount}");
            // Send HTTP POST request with amount data
            int amountValue = amount;
            _ = Task.Run(() => SendHttpPostAsync("TakeHealth", new { amount = amountValue.ToString() }));
        }
    }

    [HarmonyPatch(typeof(GameManager))]
    static class GameManager_PlayerDead_Patch
    {
        [HarmonyPatch(nameof(GameManager.PlayerDead), new[] { typeof(float) })]
        [HarmonyPrefix]
        static void Prefix()
        {
            Plugin.Logger.LogInfo($"PlayerDead");
            // Send HTTP POST request
            _ = Task.Run(() => SendHttpPostAsync("PlayerDead"));
        }
    }
}