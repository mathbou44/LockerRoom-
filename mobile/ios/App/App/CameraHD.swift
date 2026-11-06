// SlabCoach - 5 nov 2026 (Mathieu : « on doit avoir la meilleure qualite possible pour la pre-evaluation avec notre IA »)
//
// La camera native en pleine resolution (48 Mpx sur iPhone 14 Pro et plus recents, et tous les iPhone 15, 16, 17) :
// la vue web ne donne que le flux video (8-12 Mpx, traitement video). Ici : AVCapturePhotoOutput, la priorite a la
// QUALITE (Deep Fusion), l'objectif qui donne le plus de pixels par mm a sa distance de mise au point minimale, et la
// photo est recadree sur le cadre (+ une marge : jamais une carte coupee) sans etre reduite.
//
// JS : Capacitor.Plugins.CameraHD
//   infos()            -> {ok, mpx, objectif, pxmm}
//   prendre({mode, etapes, aides, textes})
//      mode : "carte" (le cadre d'une carte, recadre) | "coin" (gros plan, photo entiere) | "surface" (photo entiere)
//      -> {annule, refus?, photos: [{data (JPEG base64), w, h, cadre ([[x,y]x4] 0..1000 dans la photo), mpx, objectif}]}
import UIKit
import AVFoundation
import ImageIO
import Capacitor

// Le controleur de l'app : le meme que Capacitor, plus la camera HD
class SCBridgeViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(CameraHDPlugin())
    }
}

@objc(CameraHDPlugin)
public class CameraHDPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "CameraHDPlugin"
    public let jsName = "CameraHD"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "infos", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "prendre", returnType: CAPPluginReturnPromise)
    ]

    @objc public func infos(_ call: CAPPluginCall) {
        guard let c = ChoixCamera.meilleur(mode: "carte") else { call.resolve(["ok": false]); return }
        call.resolve(["ok": true, "mpx": c.mpx, "objectif": c.nom, "pxmm": c.pxmm])
    }

    @objc public func prendre(_ call: CAPPluginCall) {
        let mode = call.getString("mode") ?? "carte"
        var etapes = (call.getArray("etapes") ?? []).compactMap { $0 as? String }
        if etapes.isEmpty { etapes = ["Photo"] }
        let aides = (call.getArray("aides") ?? []).compactMap { $0 as? String }
        var textes: [String: String] = [:]
        if let t = call.getObject("textes") { for (k, v) in t { if let s = v as? String { textes[k] = s } } }
        let ouvrir = { [weak self] in
            guard let self = self, let parent = self.bridge?.viewController else { call.resolve(["annule": true]); return }
            guard let choix = ChoixCamera.meilleur(mode: mode) else { call.resolve(["annule": true, "erreur": "camera"]); return }
            let vc = CameraHDVC(choix: choix, mode: mode, etapes: etapes, aides: aides, textes: textes)
            vc.modalPresentationStyle = .fullScreen
            vc.fini = { resultat in call.resolve(resultat) }
            parent.present(vc, animated: true)
        }
        DispatchQueue.main.async {
            switch AVCaptureDevice.authorizationStatus(for: .video) {
            case .authorized: ouvrir()
            case .notDetermined:
                AVCaptureDevice.requestAccess(for: .video) { ok in
                    DispatchQueue.main.async { if ok { ouvrir() } else { call.resolve(["annule": true, "refus": true]) } }
                }
            default: call.resolve(["annule": true, "refus": true])
            }
        }
    }
}

// L'objectif et le format : le plus de pixels par millimetre de carte, a la distance ou la mise au point est possible
struct ChoixCamera {
    let device: AVCaptureDevice
    let format: AVCaptureDevice.Format
    let largeur: Int            // la photo (capteur, paysage)
    let hauteur: Int
    let fraction: Double        // la largeur de la carte (+ un peu d'air) en part du petit cote du capteur
    let pxmm: Double
    let nom: String
    var mpx: Double { (Double(largeur) * Double(hauteur) / 1e6 * 10).rounded() / 10 }

    static let carteMM = 66.0                       // 63,5 mm + un peu d'air

    static func dimensionsMax(_ f: AVCaptureDevice.Format) -> (Int, Int) {
        if #available(iOS 16.0, *) {
            let m = f.supportedMaxPhotoDimensions.max { Int($0.width) * Int($0.height) < Int($1.width) * Int($1.height) }
            if let m = m { return (Int(m.width), Int(m.height)) }
        }
        let d = f.highResolutionStillImageDimensions
        return (Int(d.width), Int(d.height))
    }

    static func meilleur(mode: String) -> ChoixCamera? {
        var l: [ChoixCamera] = []
        // 7 nov 2026 (Mathieu : « la camera ouvre en fish eye, ne devrait pas ; on est trop proche ») : toujours l'objectif
        // principal (grand-angle, 48 Mpx) ; l'ultra grand-angle deformait la carte (fish eye) et forcait a coller le telephone
        let types: [(AVCaptureDevice.DeviceType, String)] = [(.builtInWideAngleCamera, "grand-angle")]
        for (type, nom) in types {
            guard let d = AVCaptureDevice.default(type, for: .video, position: .back) else { continue }
            // le format qui donne la plus grande photo (a egalite : celui qui accepte la meilleure qualite photo)
            var best: AVCaptureDevice.Format?
            var bestPx = 0
            for f in d.formats {
                let (w, h) = dimensionsMax(f)
                let px = w * h
                if px > bestPx || (px == bestPx && f.isHighPhotoQualitySupported && !(best?.isHighPhotoQualitySupported ?? false)) {
                    best = f; bestPx = px
                }
            }
            guard let f = best else { continue }
            let (w, h) = dimensionsMax(f)
            let fov = Double(f.videoFieldOfView) * .pi / 180          // le grand cote
            let tanC = tan(fov / 2) * Double(min(w, h)) / Double(max(w, h))   // le petit cote
            let minF = d.minimumFocusDistance > 0 ? Double(d.minimumFocusDistance) : (type == .builtInWideAngleCamera ? 200 : 40)
            var dist: Double
            if mode == "carte" {
                // assez loin pour la mise au point (+12 %), et la carte au plus a 80 % du petit cote (elle entre dans le cadre)
                dist = max(minF * 1.12, carteMM / (0.80 * 2 * tanC))
            } else {
                dist = max(minF * 1.15, 50)                            // gros plan : au plus pres (pas moins de 5 cm : l'ombre)
            }
            let champ = 2 * dist * tanC
            let pxmm = Double(min(w, h)) / champ
            l.append(ChoixCamera(device: d, format: f, largeur: max(w, h), hauteur: min(w, h),
                                 fraction: min(0.8, carteMM / champ), pxmm: pxmm, nom: nom))
        }
        guard !l.isEmpty else { return nil }
        // le grand-angle a la meilleure optique : l'ultra grand-angle seulement s'il donne nettement plus de detail
        let ga = l.first { $0.nom == "grand-angle" }
        let mx = l.max { $0.pxmm < $1.pxmm }!
        if let ga = ga, mx.nom != ga.nom, mx.pxmm < ga.pxmm * 1.2 { return ga }
        return mx
    }
}

final class CameraHDVC: UIViewController, AVCapturePhotoCaptureDelegate {
    let choix: ChoixCamera
    let mode: String
    let etapes: [String]
    let aides: [String]
    let textes: [String: String]
    var fini: (([String: Any]) -> Void)?

    private let session = AVCaptureSession()
    private let sortie = AVCapturePhotoOutput()
    private let file = DispatchQueue(label: "slabcoach.camerahd")
    private var apercu: AVCaptureVideoPreviewLayer!
    private var cadreNorm = CGRect.zero               // le cadre, en coordonnees du capteur (0..1, paysage)
    private let cadreCalque = CAShapeLayer()
    private let ombre = CAShapeLayer()
    private var photos: [[String: Any]] = []
    private var i = 0
    private var occupe = false
    private var termine = false
    private var obsFocus: NSKeyValueObservation?

    private let titre = UILabel()
    private let aide = UILabel()
    private let etat = UILabel()
    private let declic = UIButton(type: .custom)
    private let fermer = UIButton(type: .system)
    private let passer = UIButton(type: .system)
    private let vignette = UIImageView()
    private let roue = UIActivityIndicatorView(style: .large)
    // 7 nov 2026 (« on devrait avoir l'option de zoomer ou non ») : 1x par defaut, 1,5x, 2x, ou en pincant (1x a 3x)
    private var zoom: CGFloat = 1
    private var zoomDepart: CGFloat = 1
    private let zooms: [CGFloat] = [1, 1.5, 2]
    private var boutonsZoom: [UIButton] = []
    private let rangeeZoom = UIStackView()

    init(choix: ChoixCamera, mode: String, etapes: [String], aides: [String], textes: [String: String]) {
        self.choix = choix; self.mode = mode; self.etapes = etapes; self.aides = aides; self.textes = textes
        super.init(nibName: nil, bundle: nil)
    }
    required init?(coder: NSCoder) { fatalError("init(coder:) non utilise") }

    override var prefersStatusBarHidden: Bool { true }
    override var supportedInterfaceOrientations: UIInterfaceOrientationMask { .portrait }

    private func t(_ k: String, _ d: String) -> String { textes[k] ?? d }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        apercu = AVCaptureVideoPreviewLayer(session: session)
        apercu.videoGravity = .resizeAspect                      // tout le capteur est visible : ce qu'on voit est ce qu'on garde
        view.layer.addSublayer(apercu)
        ombre.fillRule = .evenOdd
        ombre.fillColor = UIColor.black.withAlphaComponent(0.45).cgColor
        view.layer.addSublayer(ombre)
        cadreCalque.strokeColor = UIColor.white.cgColor
        cadreCalque.fillColor = UIColor.clear.cgColor
        cadreCalque.lineWidth = 4
        cadreCalque.lineCap = .round
        view.layer.addSublayer(cadreCalque)
        construireUI()
        configurer()
        let tap = UITapGestureRecognizer(target: self, action: #selector(toucher(_:)))
        view.addGestureRecognizer(tap)
        let pince = UIPinchGestureRecognizer(target: self, action: #selector(pincer(_:)))
        view.addGestureRecognizer(pince)
    }

    private func zoomMax() -> CGFloat {
        return min(3, max(1, choix.device.activeFormat.videoMaxZoomFactor))
    }

    private func appliquerZoom(_ z: CGFloat) {
        let d = choix.device
        let z2 = max(1, min(z, zoomMax()))
        do {
            try d.lockForConfiguration()
            d.videoZoomFactor = z2
            d.unlockForConfiguration()
        } catch { return }
        zoom = z2
        placerCadre()
        majBoutonsZoom()
    }

    private func majBoutonsZoom() {
        for (k, b) in boutonsZoom.enumerated() {
            let on = abs(zooms[k] - zoom) < 0.05
            b.backgroundColor = on ? UIColor.white.withAlphaComponent(0.9) : UIColor.black.withAlphaComponent(0.45)
            b.setTitleColor(on ? .black : .white, for: .normal)
            b.isHidden = zooms[k] > zoomMax() + 0.01
        }
    }

    @objc private func choisirZoom(_ b: UIButton) {
        guard b.tag >= 0, b.tag < zooms.count else { return }
        UISelectionFeedbackGenerator().selectionChanged()
        appliquerZoom(zooms[b.tag])
    }

    @objc private func pincer(_ g: UIPinchGestureRecognizer) {
        if g.state == .began { zoomDepart = zoom }
        if g.state == .changed || g.state == .ended { appliquerZoom(zoomDepart * g.scale) }
    }

    private func construireUI() {
        for l in [titre, aide, etat] {
            l.textColor = .white; l.textAlignment = .center; l.numberOfLines = 0
            l.translatesAutoresizingMaskIntoConstraints = false; view.addSubview(l)
        }
        titre.font = .systemFont(ofSize: 20, weight: .bold)
        aide.font = .systemFont(ofSize: 15, weight: .regular)
        aide.textColor = UIColor.white.withAlphaComponent(0.85)
        etat.font = .systemFont(ofSize: 13, weight: .semibold)
        etat.textColor = UIColor(red: 0.49, green: 0.89, blue: 0.66, alpha: 1)

        declic.translatesAutoresizingMaskIntoConstraints = false
        declic.layer.cornerRadius = 38
        declic.layer.borderWidth = 5
        declic.layer.borderColor = UIColor.white.cgColor
        declic.backgroundColor = UIColor.white.withAlphaComponent(0.25)
        declic.accessibilityLabel = t("declic", "Prendre la photo")
        declic.addTarget(self, action: #selector(capturer), for: .touchUpInside)
        view.addSubview(declic)

        fermer.translatesAutoresizingMaskIntoConstraints = false
        fermer.setTitle("✕", for: .normal)
        fermer.titleLabel?.font = .systemFont(ofSize: 24, weight: .semibold)
        fermer.tintColor = .white
        fermer.accessibilityLabel = t("fermer", "Fermer")
        fermer.addTarget(self, action: #selector(annuler), for: .touchUpInside)
        view.addSubview(fermer)

        passer.translatesAutoresizingMaskIntoConstraints = false
        passer.setTitle(t("passer", "Passer"), for: .normal)
        passer.titleLabel?.font = .systemFont(ofSize: 15, weight: .semibold)
        passer.tintColor = .white
        passer.isHidden = true
        passer.addTarget(self, action: #selector(sauter), for: .touchUpInside)
        view.addSubview(passer)

        vignette.translatesAutoresizingMaskIntoConstraints = false
        vignette.contentMode = .scaleAspectFill
        vignette.clipsToBounds = true
        vignette.layer.cornerRadius = 6
        vignette.layer.borderWidth = 1.5
        vignette.layer.borderColor = UIColor.white.withAlphaComponent(0.8).cgColor
        vignette.isHidden = true
        view.addSubview(vignette)

        roue.translatesAutoresizingMaskIntoConstraints = false
        roue.color = .white
        roue.hidesWhenStopped = true
        view.addSubview(roue)

        rangeeZoom.axis = .horizontal
        rangeeZoom.spacing = 10
        rangeeZoom.translatesAutoresizingMaskIntoConstraints = false
        for (k, z) in zooms.enumerated() {
            let b = UIButton(type: .custom)
            b.tag = k
            b.setTitle(z == 1 ? "1×" : z == 2 ? "2×" : "1,5×", for: .normal)
            b.titleLabel?.font = .systemFont(ofSize: 14, weight: .bold)
            b.layer.cornerRadius = 19
            b.translatesAutoresizingMaskIntoConstraints = false
            b.widthAnchor.constraint(equalToConstant: 50).isActive = true
            b.heightAnchor.constraint(equalToConstant: 38).isActive = true
            b.addTarget(self, action: #selector(choisirZoom(_:)), for: .touchUpInside)
            boutonsZoom.append(b)
            rangeeZoom.addArrangedSubview(b)
        }
        view.addSubview(rangeeZoom)

        let g = view.safeAreaLayoutGuide
        NSLayoutConstraint.activate([
            fermer.topAnchor.constraint(equalTo: g.topAnchor, constant: 8),
            fermer.leadingAnchor.constraint(equalTo: g.leadingAnchor, constant: 12),
            fermer.widthAnchor.constraint(equalToConstant: 44), fermer.heightAnchor.constraint(equalToConstant: 44),
            titre.topAnchor.constraint(equalTo: g.topAnchor, constant: 14),
            titre.leadingAnchor.constraint(equalTo: g.leadingAnchor, constant: 60),
            titre.trailingAnchor.constraint(equalTo: g.trailingAnchor, constant: -60),
            aide.topAnchor.constraint(equalTo: titre.bottomAnchor, constant: 6),
            aide.leadingAnchor.constraint(equalTo: g.leadingAnchor, constant: 24),
            aide.trailingAnchor.constraint(equalTo: g.trailingAnchor, constant: -24),
            declic.bottomAnchor.constraint(equalTo: g.bottomAnchor, constant: -22),
            declic.centerXAnchor.constraint(equalTo: g.centerXAnchor),
            declic.widthAnchor.constraint(equalToConstant: 76), declic.heightAnchor.constraint(equalToConstant: 76),
            rangeeZoom.bottomAnchor.constraint(equalTo: declic.topAnchor, constant: -14),
            rangeeZoom.centerXAnchor.constraint(equalTo: g.centerXAnchor),
            etat.bottomAnchor.constraint(equalTo: rangeeZoom.topAnchor, constant: -10),
            etat.leadingAnchor.constraint(equalTo: g.leadingAnchor, constant: 20),
            etat.trailingAnchor.constraint(equalTo: g.trailingAnchor, constant: -20),
            passer.centerYAnchor.constraint(equalTo: declic.centerYAnchor),
            passer.trailingAnchor.constraint(equalTo: g.trailingAnchor, constant: -20),
            vignette.centerYAnchor.constraint(equalTo: declic.centerYAnchor),
            vignette.leadingAnchor.constraint(equalTo: g.leadingAnchor, constant: 24),
            vignette.widthAnchor.constraint(equalToConstant: 46), vignette.heightAnchor.constraint(equalToConstant: 64),
            roue.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            roue.centerYAnchor.constraint(equalTo: view.centerYAnchor)
        ])
        majTextes()
        majBoutonsZoom()
    }

    private func majTextes() {
        titre.text = etapes[min(i, etapes.count - 1)]
        aide.text = i < aides.count ? aides[i] : ""
        passer.isHidden = i == 0 || occupe
    }

    private func configurer() {
        let d = choix.device
        session.beginConfiguration()
        guard let entree = try? AVCaptureDeviceInput(device: d), session.canAddInput(entree), session.canAddOutput(sortie) else {
            session.commitConfiguration(); return
        }
        session.addInput(entree)
        session.addOutput(sortie)
        do {
            try d.lockForConfiguration()
            d.activeFormat = choix.format
            if d.isFocusModeSupported(.continuousAutoFocus) { d.focusMode = .continuousAutoFocus }
            if d.isAutoFocusRangeRestrictionSupported { d.autoFocusRangeRestriction = mode == "surface" ? AVCaptureDevice.AutoFocusRangeRestriction.none : AVCaptureDevice.AutoFocusRangeRestriction.near }
            if d.isExposureModeSupported(.continuousAutoExposure) { d.exposureMode = .continuousAutoExposure }
            if d.isSmoothAutoFocusSupported { d.isSmoothAutoFocusEnabled = false }
            d.unlockForConfiguration()
        } catch {}
        sortie.maxPhotoQualityPrioritization = .quality
        if #available(iOS 16.0, *) {
            let dims = choix.format.supportedMaxPhotoDimensions.max { Int($0.width) * Int($0.height) < Int($1.width) * Int($1.height) }
            if let dims = dims { sortie.maxPhotoDimensions = dims }
        } else {
            sortie.isHighResolutionCaptureEnabled = true
        }
        if sortie.isContentAwareDistortionCorrectionSupported { sortie.isContentAwareDistortionCorrectionEnabled = true }
        session.commitConfiguration()
        orienter(apercu.connection)
        orienter(sortie.connection(with: .video))
        obsFocus = d.observe(\.isAdjustingFocus, options: [.new]) { [weak self] dev, _ in
            DispatchQueue.main.async { self?.etat.text = dev.isAdjustingFocus ? (self?.t("focus", "Mise au point…") ?? "") : "" }
        }
        file.async { [weak self] in
            self?.session.startRunning()
            DispatchQueue.main.async {
                // 7 nov 2026 (« ca marche tres mal ») : a la distance de mise au point, la carte ne remplit qu'une petite
                // partie de l'image en 1x ; le zoom de depart la fait remplir le cadre (2x au plus), sans s'approcher
                if let s = self, s.mode == "carte" {
                    let z0 = CGFloat(min(2.0, max(1.0, 0.62 / max(0.05, s.choix.fraction))))
                    let proche = s.zooms.min { abs($0 - z0) < abs($1 - z0) } ?? 1
                    s.appliquerZoom(proche)
                }
                self?.view.setNeedsLayout()
            }
        }
    }

    private func orienter(_ c: AVCaptureConnection?) {
        guard let c = c else { return }
        if #available(iOS 17.0, *) {
            if c.isVideoRotationAngleSupported(90) { c.videoRotationAngle = 90 }
        } else if c.isVideoOrientationSupported {
            c.videoOrientation = .portrait
        }
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        apercu.frame = view.bounds
        placerCadre()
        majBoutonsZoom()
    }

    // le cadre : la carte en portrait. Sa largeur suit le petit cote du capteur (y du capteur), sa hauteur le grand (x)
    private func placerCadre() {
        guard mode == "carte" else { cadreCalque.path = nil; ombre.path = nil; return }
        let rapportCapteur = Double(choix.hauteur) / Double(choix.largeur)        // 0,75 en 4:3
        let fy = min(0.8, choix.fraction * Double(zoom))            // le zoom agrandit la carte dans le cadre
        let fx = min(0.94, fy * (88.9 / 63.5) * rapportCapteur)
        cadreNorm = CGRect(x: 0.5 - fx / 2, y: 0.5 - fy / 2, width: fx, height: fy)
        let r = apercu.layerRectConverted(fromMetadataOutputRect: cadreNorm)
        guard r.width > 10, r.height > 10 else { return }
        let p = UIBezierPath(rect: view.bounds)
        p.append(UIBezierPath(roundedRect: r, cornerRadius: 10))
        ombre.path = p.cgPath
        let L = min(r.width, r.height) * 0.16
        let c = UIBezierPath()
        for (x, y, dx, dy) in [(r.minX, r.minY, 1.0, 1.0), (r.maxX, r.minY, -1.0, 1.0), (r.maxX, r.maxY, -1.0, -1.0), (r.minX, r.maxY, 1.0, -1.0)] {
            c.move(to: CGPoint(x: x + CGFloat(dx) * L, y: y)); c.addLine(to: CGPoint(x: x, y: y)); c.addLine(to: CGPoint(x: x, y: y + CGFloat(dy) * L))
        }
        cadreCalque.path = c.cgPath
    }

    @objc private func toucher(_ g: UITapGestureRecognizer) {
        let p = g.location(in: view)
        let pt = apercu.captureDevicePointConverted(fromLayerPoint: p)
        let d = choix.device
        do {
            try d.lockForConfiguration()
            if d.isFocusPointOfInterestSupported { d.focusPointOfInterest = pt; d.focusMode = .autoFocus }
            if d.isExposurePointOfInterestSupported { d.exposurePointOfInterest = pt; d.exposureMode = .autoExpose }
            d.isSubjectAreaChangeMonitoringEnabled = true
            d.unlockForConfiguration()
        } catch {}
        // apres le point choisi, on revient en continu quand la scene bouge
        NotificationCenter.default.removeObserver(self, name: .AVCaptureDeviceSubjectAreaDidChange, object: d)
        NotificationCenter.default.addObserver(self, selector: #selector(sceneBouge), name: .AVCaptureDeviceSubjectAreaDidChange, object: d)
    }

    @objc private func sceneBouge() {
        let d = choix.device
        do {
            try d.lockForConfiguration()
            if d.isFocusModeSupported(.continuousAutoFocus) { d.focusMode = .continuousAutoFocus }
            if d.isExposureModeSupported(.continuousAutoExposure) { d.exposureMode = .continuousAutoExposure }
            d.isSubjectAreaChangeMonitoringEnabled = false
            d.unlockForConfiguration()
        } catch {}
        NotificationCenter.default.removeObserver(self, name: .AVCaptureDeviceSubjectAreaDidChange, object: d)
    }

    @objc private func capturer() {
        guard !occupe, session.isRunning else { return }
        occupe = true
        declic.isEnabled = false; declic.alpha = 0.5; passer.isHidden = true
        let r = AVCapturePhotoSettings()
        r.flashMode = .off
        r.photoQualityPrioritization = .quality
        if #available(iOS 16.0, *) {
            r.maxPhotoDimensions = sortie.maxPhotoDimensions
        } else {
            r.isHighResolutionPhotoEnabled = true
        }
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        etat.text = t("traitement", "Photo en pleine résolution…")
        roue.startAnimating()
        sortie.capturePhoto(with: r, delegate: self)
    }

    func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        let cadre = cadreNorm, mode = self.mode
        file.async { [weak self] in
            let res = (error == nil) ? CameraHDVC.preparer(photo: photo, cadre: cadre, mode: mode) : nil
            DispatchQueue.main.async { self?.recue(res) }
        }
    }

    private func recue(_ res: ([String: Any], UIImage)?) {
        roue.stopAnimating()
        occupe = false
        declic.isEnabled = true; declic.alpha = 1
        guard let res = res else {
            etat.text = t("erreur", "Photo ratée : reprends-la")
            majTextes(); return
        }
        let (p, mini) = res
        var d = p
        d["mpx"] = choix.mpx
        d["objectif"] = choix.nom
        photos.append(d)
        UINotificationFeedbackGenerator().notificationOccurred(.success)
        vignette.image = mini; vignette.isHidden = false
        let flash = UIView(frame: view.bounds); flash.backgroundColor = .white; flash.alpha = 0.7; view.addSubview(flash)
        UIView.animate(withDuration: 0.25, animations: { flash.alpha = 0 }) { _ in flash.removeFromSuperview() }
        etat.text = ""
        i += 1
        if i >= etapes.count { terminer(annule: false) } else { majTextes() }
    }

    @objc private func sauter() { terminer(annule: false) }
    @objc private func annuler() { terminer(annule: true) }

    private func terminer(annule: Bool) {
        guard !termine else { return }
        termine = true
        obsFocus?.invalidate()
        NotificationCenter.default.removeObserver(self)
        file.async { [weak self] in self?.session.stopRunning() }
        let r: [String: Any] = ["annule": annule || photos.isEmpty, "photos": annule ? [] : photos]
        dismiss(animated: true) { [weak self] in self?.fini?(r) }
    }

    // -- la photo : recadree sur le cadre + une marge (jamais une carte coupee), redressee, en JPEG de grande qualite --
    static func preparer(photo: AVCapturePhoto, cadre: CGRect, mode: String) -> ([String: Any], UIImage)? {
        guard let cg = photo.cgImageRepresentation() else { return nil }
        let o = (photo.metadata[kCGImagePropertyOrientation as String] as? NSNumber)?.uint32Value ?? 1
        let W = CGFloat(cg.width), H = CGFloat(cg.height)
        var image = cg
        var quad: [[Int]] = []
        if mode == "carte" && cadre.width > 0 {
            // la marge : 25 % de chaque cote (7 nov 2026 : une carte plus grande que le cadre n'est jamais coupee ; l'app
            // recadre ensuite sur ses vrais bords), moins si le cadre est pres du bord du capteur
            let mx = max(0, min(0.25, cadre.minX / cadre.width, (1 - cadre.maxX) / cadre.width))
            let my = max(0, min(0.25, cadre.minY / cadre.height, (1 - cadre.maxY) / cadre.height))
            let n = cadre.insetBy(dx: -cadre.width * mx, dy: -cadre.height * my)
            // le capteur en paysage (le cas normal) ; sinon l'image est deja tournee d'un quart de tour
            let rp: CGRect = W >= H
                ? CGRect(x: n.minX * W, y: n.minY * H, width: n.width * W, height: n.height * H)
                : CGRect(x: (1 - n.maxY) * W, y: n.minX * H, width: n.height * W, height: n.width * H)
            if let c = cg.cropping(to: rp.integral) { image = c }
            // la position du cadre dans la photo recadree (symetrique sur chaque axe : l'orientation n'y change rien,
            // sauf l'echange des axes pour un quart de tour)
            let ux = mx / (1 + 2 * mx), uy = my / (1 + 2 * my)
            let quartDeTour = [5, 6, 7, 8].contains(Int(o)) != (W < H)
            let (h, v) = quartDeTour ? (uy, ux) : (ux, uy)
            let a = Int((h * 1000).rounded()), b = Int((v * 1000).rounded())
            quad = [[a, b], [1000 - a, b], [1000 - a, 1000 - b], [a, 1000 - b]]
        }
        let ui = UIImage(cgImage: image, scale: 1, orientation: CameraHDVC.orientation(o))
        // pas de reduction pour la carte (jusqu'a 5000 px) ; gros plans et surface : 4032 px suffisent
        let maxCote: CGFloat = mode == "carte" ? 5000 : 4032
        let k = min(1, maxCote / max(ui.size.width, ui.size.height))
        let taille = CGSize(width: (ui.size.width * k).rounded(), height: (ui.size.height * k).rounded())
        let f = UIGraphicsImageRendererFormat.default()
        f.scale = 1
        f.opaque = true
        let droite = UIGraphicsImageRenderer(size: taille, format: f).image { _ in ui.draw(in: CGRect(origin: .zero, size: taille)) }
        // le serveur garde jusqu'a 8 Mo (eBay : 7 Mo) : la meilleure qualite sous 6,5 Mo
        let limite = mode == "carte" ? 6_500_000 : 4_000_000
        var data: Data?
        for q in [0.93, 0.88, 0.82, 0.75] as [CGFloat] {
            data = droite.jpegData(compressionQuality: q)
            if let d = data, d.count <= limite { break }
        }
        guard let jpeg = data else { return nil }
        let mk = 140 / max(taille.width, taille.height)
        let mini = UIGraphicsImageRenderer(size: CGSize(width: taille.width * mk, height: taille.height * mk), format: f).image { _ in
            droite.draw(in: CGRect(x: 0, y: 0, width: taille.width * mk, height: taille.height * mk))
        }
        var r: [String: Any] = ["data": jpeg.base64EncodedString(), "w": Int(taille.width), "h": Int(taille.height)]
        if !quad.isEmpty { r["cadre"] = quad }
        return (r, mini)
    }

    static func orientation(_ o: UInt32) -> UIImage.Orientation {
        switch o {
        case 2: return .upMirrored
        case 3: return .down
        case 4: return .downMirrored
        case 5: return .leftMirrored
        case 6: return .right
        case 7: return .rightMirrored
        case 8: return .left
        default: return .up
        }
    }
}
