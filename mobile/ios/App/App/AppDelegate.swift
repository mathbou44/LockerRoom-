import UIKit
import Capacitor

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?

    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Override point for customization after application launch.
        return true
    }

    func applicationWillResignActive(_ application: UIApplication) {
        // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
        // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
    }

    func applicationDidEnterBackground(_ application: UIApplication) {
        // 9 nov 2026 (Aikido) : l'apercu du selecteur d'apps ne montre jamais l'ecran (prix, inventaire, compte)
        AppDelegate.masquerEcran(window)
    }

    func applicationWillEnterForeground(_ application: UIApplication) {
        // Called as part of the transition from the background to the active state; here you can undo many of the changes made on entering the background.
    }

    func applicationDidBecomeActive(_ application: UIApplication) {
        AppDelegate.demasquerEcran(window)
    }

    func applicationWillTerminate(_ application: UIApplication) {
        // Called when the application is about to terminate. Save data if appropriate. See also applicationDidEnterBackground:.
    }

    // LockerRoom : notifications d'alertes de prix (plugin PushNotifications de Capacitor)
    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        NotificationCenter.default.post(name: .capacitorDidRegisterForRemoteNotifications, object: deviceToken)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        NotificationCenter.default.post(name: .capacitorDidFailToRegisterForRemoteNotifications, object: error)
    }

    func application(_ application: UIApplication,
                     configurationForConnecting connectingSceneSession: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        let config = UISceneConfiguration(name: "Default Configuration",
                                          sessionRole: connectingSceneSession.role)
        config.delegateClass = SceneDelegate.self
        return config
    }
}

// 9 nov 2026 (Aikido, « on-screen data should be hidden when backgrounding ») : quand l'app passe en arriere-plan, un flou
// sombre couvre l'ecran ; l'apercu du selecteur d'apps ne montre ni prix, ni inventaire, ni compte. Retire au retour.
extension AppDelegate {
    static let etiquetteEcranPrive = 0x5C0A

    static func masquerEcran(_ window: UIWindow?) {
        guard let w = window, w.viewWithTag(etiquetteEcranPrive) == nil else { return }
        let flou = UIVisualEffectView(effect: UIBlurEffect(style: .dark))
        flou.frame = w.bounds
        flou.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        flou.tag = etiquetteEcranPrive
        w.addSubview(flou)
    }

    static func demasquerEcran(_ window: UIWindow?) {
        window?.viewWithTag(etiquetteEcranPrive)?.removeFromSuperview()
    }
}
