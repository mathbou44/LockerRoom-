import UIKit
import Capacitor

class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = scene as? UIWindowScene else { return }

        window = UIWindow(windowScene: windowScene)
        window?.rootViewController = SCBridgeViewController()   // 5 nov 2026 : + la camera HD (CameraHD.swift)
        window?.makeKeyAndVisible()

        SceneDelegateProxy.shared.scene(scene, willConnectTo: session, options: connectionOptions)
    }

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        SceneDelegateProxy.shared.scene(scene, openURLContexts: URLContexts)
    }

    func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
        SceneDelegateProxy.shared.scene(scene, continue: userActivity)
    }

    // 9 nov 2026 (Aikido) : l'apercu du selecteur d'apps est flou (voir AppDelegate.masquerEcran)
    func sceneDidEnterBackground(_ scene: UIScene) {
        AppDelegate.masquerEcran(window)
    }

    func sceneWillEnterForeground(_ scene: UIScene) {
        AppDelegate.demasquerEcran(window)
    }

    func sceneDidBecomeActive(_ scene: UIScene) {
        AppDelegate.demasquerEcran(window)
    }
}
