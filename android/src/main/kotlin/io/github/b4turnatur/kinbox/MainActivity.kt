package io.github.b4turnatur.kinbox

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.DownloadManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ActivityNotFoundException
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.webkit.JavascriptInterface
import android.webkit.JsPromptResult
import android.webkit.JsResult
import android.webkit.MimeTypeMap
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.Toast
import android.window.OnBackInvokedDispatcher
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLDecoder
import java.net.URLEncoder
import java.util.UUID
import kotlin.concurrent.thread

// Die App zeigt Popup und Einstellungen der Browser-Erweiterung in einer WebView an (Dateien unter /kbapp/,
// ausgeliefert aus den Assets unter der Adresse des Servers – so gibt es keine Cross-Origin-Probleme).
// assets/app.js ersetzt die chrome.*-Schnittstellen; was Android selbst können muss, liegt hier in Bridge.
class MainActivity : Activity() {
    private lateinit var web: WebView
    private lateinit var root: FrameLayout
    private val key = UUID.randomUUID().toString()   // nur unsere eigenen Seiten kennen ihn (nicht z. B. der YouTube-Player)
    private var full: View? = null
    private var fullCb: WebChromeClient.CustomViewCallback? = null
    private var fileCb: ValueCallback<Array<Uri>>? = null
    private var pastePending = false

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        Box.init(this)
        web = WebView(this)
        root = FrameLayout(this).apply { addView(web) }
        setContentView(root)
        if (Build.VERSION.SDK_INT >= 35) root.setOnApplyWindowInsetsListener { v, i ->   // Android 15+: Inhalt nicht unter Statusleiste/Tastatur
            val s = i.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.ime())
            v.setPadding(s.left, s.top, s.right, s.bottom)
            WindowInsets.CONSUMED
        }
        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            userAgentString += " KinboxApp"
        }
        web.addJavascriptInterface(Bridge(), "KinboxApp")
        web.webViewClient = Client()
        web.webChromeClient = Chrome()
        web.setDownloadListener { url, _, cd, mime, _ -> Box.download(url, fileName(cd) ?: URLUtil.guessFileName(url, cd, mime)) }
        if (Build.VERSION.SDK_INT >= 33)
            onBackInvokedDispatcher.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT) { back() }
        // Nach Prozess-Tod oder aus „Zuletzt verwendet“ kommt der alte Intent noch einmal – nicht erneut auswerten
        open(if (state == null && intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY == 0) intent else Intent())
    }

    override fun onResume() {
        super.onResume()
        Box.poll()
    }

    override fun onNewIntent(i: Intent) {
        super.onNewIntent(i)
        open(i)
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }

    @Deprecated("bis Android 12")
    override fun onBackPressed() = back()

    private fun back() = when {
        full != null -> (web.webChromeClient as Chrome).onHideCustomView()
        web.canGoBack() -> web.goBack()
        else -> finish()
    }

    // ---- Start: geteilter Link, Einladungslink, Zwischenablage oder einfach die App ----

    private fun open(i: Intent) {
        if (i.action == ACTION_PASTE) { pastePending = true; return load("popup.html?window=1") }
        open(when (i.action) {
            Intent.ACTION_SEND -> i.getStringExtra(Intent.EXTRA_TEXT)
            Intent.ACTION_VIEW -> i.dataString
            else -> null
        } ?: "", i.getStringExtra(Intent.EXTRA_SUBJECT) ?: "")
    }

    private fun open(text: String, title: String = "") {
        if (invite(text) != null) { load("popup.html?window=1"); connectAsk(text); return }
        val url = Regex("https?://\\S+").find(text)?.value
        load("popup.html?window=1" + if (url == null) "" else "&tab=1&url=${enc(url)}&title=${enc(title)}")
    }

    // Die Zwischenablage gibt Android erst frei, wenn die App den Fokus hat (Android 10+)
    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (!hasFocus || !pastePending) return
        pastePending = false
        val text = clip()
        if (Regex("(https?|kinbox)://").containsMatchIn(text)) open(text) else toast(getString(R.string.no_link))
    }

    private fun clip() = getSystemService(ClipboardManager::class.java).primaryClip?.getItemAt(0)?.coerceToText(this)?.toString() ?: ""

    private fun load(page: String) {
        val s = Box.server()
        web.loadUrl(if (s.isEmpty()) "$SETUP_ORIGIN/kbapp/setup.html" else "$s/kbapp/$page")
    }

    /** Server + Token aus Einladungslink (…/library?token=…) oder kinbox://setup?server=…&token=… */
    private fun invite(text: String): Pair<String, String>? {
        val u = Regex("(https?|kinbox)://\\S+").find(text)?.value?.let(Uri::parse) ?: return null
        val token = u.getQueryParameter("token")?.takeIf { it.isNotBlank() } ?: return null
        val server = when {
            u.scheme == "kinbox" -> u.getQueryParameter("server")?.let(Uri::parse)
                ?.takeIf { it.scheme in listOf("http", "https") && !it.host.isNullOrEmpty() }
                ?.let { "${it.scheme}://${it.encodedAuthority}${it.encodedPath ?: ""}" } ?: return null
            u.path?.trimEnd('/') == "/library" -> "${u.scheme}://${u.encodedAuthority}"
            else -> return null
        }
        return server.trimEnd('/') to token
    }

    private fun connectAsk(text: String) {
        val (server, token) = invite(text) ?: return toast(getString(R.string.not_invite))
        AlertDialog.Builder(this)
            .setTitle(R.string.connect_title)
            .setMessage(getString(R.string.connect_text, server))
            .setPositiveButton(R.string.connect_yes) { _, _ ->
                Box.saveStore(Box.store().put("serverUrl", server).put("token", token).toString())
                toast(getString(R.string.connected))
                load("popup.html?window=1")
                askNotify()
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    private fun askNotify() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)   // nach zweimal „Nein“ fragt Android von selbst nicht mehr
    }

    /** Eigene Seiten: Einrichtungsseite sowie Heim- und Unterwegs-Adresse */
    private fun own(u: Uri) = listOf(SETUP_ORIGIN, Box.url("serverUrl"), Box.url("serverUrl2"))
        .any { it.isNotEmpty() && u.encodedAuthority == Uri.parse(it).encodedAuthority }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_LONG).show()

    // Status- und Navigationsleiste in der Hintergrundfarbe der Seite (hell/dunkel, eigenes Farbschema)
    private fun bars() = web.evaluateJavascript("[document.body, document.documentElement].map((e) => e && getComputedStyle(e).backgroundColor)" +
        ".find((c) => c && !/^rgba\\(.*, 0\\)$/.test(c) && c !== 'transparent') || ''") { bars(it) }

    // Hell/Dunkel umgeschaltet: die Seite folgt von selbst (prefers-color-scheme), die Leisten hier nachziehen
    override fun onConfigurationChanged(c: Configuration) {
        super.onConfigurationChanged(c)
        web.postDelayed({ bars() }, 300)
    }

    private fun bars(css: String) {
        val (r, g, b) = Regex("\\d+").findAll(css).take(3).map { it.value.toInt() }.toList().takeIf { it.size == 3 } ?: return
        val c = Color.rgb(r, g, b)
        root.setBackgroundColor(c)
        @Suppress("DEPRECATION")
        if (Build.VERSION.SDK_INT < 35) { window.statusBarColor = c; window.navigationBarColor = c }
        val light = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS or WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS
        if (Build.VERSION.SDK_INT >= 30) window.insetsController?.setSystemBarsAppearance(if (Color.luminance(c) > 0.5f) light else 0, light)
    }

    // ---- Für app.js ------------------------------------------------------------

    inner class Bridge {
        @JavascriptInterface fun load(k: String): String = if (k == key) Box.store().toString() else "{}"
        @JavascriptInterface fun save(k: String, json: String) { if (k == key) Box.saveStore(json) }
        @JavascriptInterface fun download(k: String, url: String, name: String) { if (k == key) Box.download(url, name) }
        @JavascriptInterface fun track(k: String, id: String, save: Boolean) {
            if (k != key) return
            Box.track(id, save)
            if (Box.store().optBoolean("notify", true)) runOnUiThread { askNotify() }
        }
        @JavascriptInterface fun open(k: String, url: String) {
            if (k == key && Regex("^https?://", RegexOption.IGNORE_CASE).containsMatchIn(url))
                runOnUiThread { try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) } catch (_: ActivityNotFoundException) { } }
        }
        @JavascriptInterface fun connect(k: String, text: String) { if (k == key) runOnUiThread { connectAsk(text) } }
        @JavascriptInterface fun paste(k: String) { if (k == key) runOnUiThread { connectAsk(clip()) } }
    }

    inner class Client : WebViewClient() {
        override fun shouldInterceptRequest(v: WebView, r: WebResourceRequest): WebResourceResponse? {
            val path = r.url.path ?: return null
            // nur unter unseren eigenen Adressen – sonst könnte eine fremde Seite (z. B. im iframe) den Schlüssel abgreifen
            if (!path.startsWith("/kbapp/") || ".." in path || !own(r.url)) return null
            val name = path.removePrefix("/kbapp/")
            val mime = MIME[name.substringAfterLast('.')] ?: "application/octet-stream"
            return try {
                var data = assets.open(name).use { it.readBytes() }
                if (mime == "text/html") data = String(data).replaceFirst("<head>",
                    "<head><script>window.KB_KEY=\"$key\"</script><script src=\"/kbapp/app.js\"></script>").toByteArray()
                WebResourceResponse(mime, "utf-8", ByteArrayInputStream(data))
            } catch (_: Exception) {
                WebResourceResponse("text/plain", "utf-8", 404, "Not Found", null, null)
            }
        }

        // In der App bleiben nur Kinbox-Seiten; alles andere öffnet der normale Browser.
        override fun shouldOverrideUrlLoading(v: WebView, r: WebResourceRequest): Boolean {
            if (!r.isForMainFrame) return false
            val u = r.url
            if (u.scheme == "kinbox") { connectAsk(u.toString()); return true }
            if (own(u)) return false
            try { startActivity(Intent(Intent.ACTION_VIEW, u)) } catch (_: ActivityNotFoundException) { }
            return true
        }

        // Kein Netz / Server aus: statt Chromium-Fehlerseite zurück zur vorigen Seite (meist das Popup) und Hinweis.
        // Zurück erst, wenn die Fehlerseite steht (nach onPageFinished) – vorher springt goBack() mal zu weit, mal gar nicht.
        private var failed: String? = null

        override fun onReceivedError(v: WebView, r: WebResourceRequest, e: WebResourceError) {
            if (!r.isForMainFrame || e.errorCode !in listOf(ERROR_HOST_LOOKUP, ERROR_CONNECT, ERROR_TIMEOUT)) return
            toast(getString(R.string.offline))
            failed = r.url.toString()
        }

        override fun onPageFinished(v: WebView, url: String) {
            if (url == failed) { failed = null; v.post { if (v.canGoBack()) v.goBack() }; return }
            bars()
        }
    }

    inner class Chrome : WebChromeClient() {
        // Vollbild-Video in der Mediathek
        override fun onShowCustomView(view: View, cb: CustomViewCallback) {
            full = view; fullCb = cb
            (window.decorView as FrameLayout).addView(view, FrameLayout.LayoutParams(-1, -1))
            if (Build.VERSION.SDK_INT >= 30) window.insetsController?.hide(WindowInsets.Type.systemBars())
        }

        override fun onHideCustomView() {
            (window.decorView as FrameLayout).removeView(full ?: return)
            full = null
            fullCb?.onCustomViewHidden()
            if (Build.VERSION.SDK_INT >= 30) window.insetsController?.show(WindowInsets.Type.systemBars())
        }

        // alert/confirm/prompt der Mediathek (Sammlungen, Löschen …): eigene Dialoge statt „Auf der Seite http://… steht:“
        override fun onJsAlert(v: WebView, url: String, msg: String, r: JsResult) = dialog(msg, r, ask = false)
        override fun onJsConfirm(v: WebView, url: String, msg: String, r: JsResult) = dialog(msg, r)
        override fun onJsPrompt(v: WebView, url: String, msg: String, def: String?, r: JsPromptResult) =
            dialog(msg, r, EditText(this@MainActivity).apply { setText(def); setSelection(text.length); isSingleLine = true })

        private fun dialog(msg: String, r: JsResult, input: EditText? = null, ask: Boolean = true): Boolean {
            if (isFinishing) return false
            val b = AlertDialog.Builder(this@MainActivity).setTitle("Kinbox").setMessage(msg)
                .setPositiveButton(android.R.string.ok) { _, _ -> if (r is JsPromptResult && input != null) r.confirm(input.text.toString()) else r.confirm() }
                .setOnCancelListener { r.cancel() }
            if (ask) b.setNegativeButton(R.string.cancel) { _, _ -> r.cancel() }
            val pad = (20 * resources.displayMetrics.density).toInt()
            if (input != null) b.setView(FrameLayout(this@MainActivity).apply { setPadding(pad, 0, pad, 0); addView(input) })
            b.show()
            return true
        }

        // Datei-Auswahl (Presets importieren, Cookie-Datei hochladen)
        override fun onShowFileChooser(w: WebView, cb: ValueCallback<Array<Uri>>, p: FileChooserParams): Boolean {
            fileCb?.onReceiveValue(null)
            fileCb = cb
            return try { startActivityForResult(p.createIntent(), FILE_REQUEST); true } catch (_: ActivityNotFoundException) { fileCb = null; false }
        }
    }

    @Deprecated("startActivityForResult reicht hier")
    override fun onActivityResult(req: Int, res: Int, data: Intent?) {
        if (req == FILE_REQUEST) { fileCb?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(res, data)); fileCb = null }
    }

    companion object {
        const val SETUP_ORIGIN = "http://kinbox.invalid"   // nur für die Einrichtungsseite, solange kein Server bekannt ist
        const val ACTION_PASTE = "io.github.b4turnatur.kinbox.PASTE"   // App-Verknüpfung „Link aus Zwischenablage“
        const val FILE_REQUEST = 2
        val MIME = mapOf("html" to "text/html", "js" to "text/javascript", "css" to "text/css", "svg" to "image/svg+xml",
            "png" to "image/png", "json" to "application/json")
        fun enc(s: String): String = URLEncoder.encode(s, "UTF-8")

        // URLUtil.guessFileName versteht kein „filename*=UTF-8''…“ (so schickt es Kinbox für Umlaute & Co.)
        fun fileName(cd: String?): String? {
            Regex("filename\\*=UTF-8''([^;]+)", RegexOption.IGNORE_CASE).find(cd ?: return null)
                ?.let { return URLDecoder.decode(it.groupValues[1].replace("+", "%2B"), "UTF-8") }
            return Regex("filename=\"([^\"]+)\"").find(cd)?.groupValues?.get(1)
        }
    }
}

// Einstellungen, Downloads aufs Handy und das Verfolgen von Aufträgen – einmal pro Prozess, nicht pro Fenster:
// Teilen aus einer anderen App öffnet eine zweite MainActivity, die sonst doppelt geladen und benachrichtigt hätte.
object Box {
    private lateinit var app: Context
    private lateinit var prefs: SharedPreferences
    private val main = Handler(Looper.getMainLooper())
    private var polling = false
    private var lastToast = 0L

    fun init(c: Context) {
        if (::app.isInitialized) return
        app = c.applicationContext
        prefs = app.getSharedPreferences("kinbox", Context.MODE_PRIVATE)
    }

    // ---- Gespeicherte Einstellungen (entspricht chrome.storage der Erweiterung) ----

    fun store() = JSONObject(prefs.getString("store", null) ?: "{}")
    fun saveStore(json: String) = prefs.edit().putString("store", json).apply()

    fun url(key: String): String {
        val s = store().optString(key).trim().trimEnd('/')
        return if (s.isEmpty() || s.startsWith("http")) s else "http://$s"
    }

    // Heim-Adresse oder (falls die nicht antwortet) Unterwegs-Adresse; umgeschaltet in pollOnce(), JS macht das selbst (common.js)
    @Volatile private var away = false
    fun server(): String = url("serverUrl2").takeIf { away && it.isNotEmpty() } ?: url("serverUrl")

    private fun token() = store().optString("token")

    // ---- Downloads aufs Handy, Benachrichtigungen ------------------------------

    fun download(url: String, name: String) = main.post {
        if (!url.startsWith("http")) return@post toast(app.getString(R.string.no_download))
        val file = name.replace(Regex("[\\\\/:*?\"<>|]"), "_")
        val r = DownloadManager.Request(Uri.parse(url))
            .setTitle(file)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "Kinbox/$file")
        // Typ aus der Endung – ältere Server schicken „octet-stream“, dann bot Android Wallet & Co. zum Öffnen an
        MimeTypeMap.getSingleton().getMimeTypeFromExtension(file.substringAfterLast('.', "").lowercase())?.let { r.setMimeType(it) }
        try { app.getSystemService(DownloadManager::class.java).enqueue(r) } catch (_: Exception) { return@post toast(app.getString(R.string.no_download)) }
        // „Alle aufs Gerät“ lädt viele Dateien nacheinander – nicht für jede einen Hinweis stapeln
        if (SystemClock.elapsedRealtime() - lastToast > 5000) { lastToast = SystemClock.elapsedRealtime(); toast(app.getString(R.string.saving)) }
    }

    private fun toast(s: String) = Toast.makeText(app, s, Toast.LENGTH_LONG).show()

    private fun notify(title: String, text: String) {
        val nm = app.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("done", app.getString(R.string.channel), NotificationManager.IMPORTANCE_DEFAULT))
        val tap = PendingIntent.getActivity(app, 0, Intent(app, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        nm.notify((title + text).hashCode(), Notification.Builder(app, "done")
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle(title).setContentText(text).setContentIntent(tap).setAutoCancel(true).build())
    }

    // Aufträge verfolgen, bis sie fertig sind: dann Benachrichtigung und ggf. aufs Handy laden.
    // ponytail: läuft nur, solange der App-Prozess lebt (auch im Hintergrund) – für „nachts laden" später WorkManager.
    private fun tracked() = JSONObject(prefs.getString("tracked", null) ?: "{}")

    @Synchronized fun track(id: String, save: Boolean) {
        prefs.edit().putString("tracked", tracked().put(id, save).toString()).apply()
        poll()
    }

    @Synchronized fun poll() {
        if (polling || !::app.isInitialized || tracked().length() == 0) return
        polling = true
        thread {
            var fails = 0
            while (fails < 40) {   // Server ~5 min nicht erreichbar → aufgeben; beim nächsten Öffnen der App geht es weiter
                fails = try { pollOnce(); 0 } catch (_: Exception) { fails + 1 }
                synchronized(this) { if (tracked().length() == 0) { polling = false; return@thread } }
                Thread.sleep(if (fails == 0) 3000 else 8000)
            }
            synchronized(this) { polling = false }
        }
    }

    private fun pollOnce() {
        val before = synchronized(this) { tracked().keys().asSequence().toSet() }   // was während der Abfrage dazukommt, bleibt
        val jobs = try { jobs() } catch (e: Exception) {
            if (url("serverUrl2").isEmpty()) throw e
            away = !away   // Netz gewechselt → andere Adresse
            jobs()
        }
        val notifyOn = store().optBoolean("notify", true)
        synchronized(this) {
            val t = tracked()
            val seen = HashSet<String>()
            for (i in 0 until jobs.length()) {
                val j = jobs.getJSONObject(i)
                val id = j.optString("id")
                seen += id
                if (!t.has(id)) continue
                val title = j.optString("title")
                when (j.optString("status")) {
                    "finished" -> {
                        if (t.optBoolean(id)) {
                            val files = j.optJSONArray("files") ?: JSONArray()
                            for (f in 0 until files.length()) if (files.getJSONObject(f).optBoolean("exists"))
                                download("${server()}/api/jobs/$id/files/$f?token=${enc(token())}", files.getJSONObject(f).optString("name"))
                        }
                        if (notifyOn) main.post { notify(app.getString(R.string.done), title) }
                    }
                    "error" -> if (notifyOn) main.post { notify(app.getString(R.string.failed), title) }
                    "cancelled" -> {}
                    else -> continue
                }
                t.remove(id)
            }
            // Auftrag woanders gelöscht/aufgeräumt (oder anderer Server/Token) → nicht ewig weiter abfragen
            (before - seen).forEach { t.remove(it) }
            prefs.edit().putString("tracked", t.toString()).apply()
        }
    }

    private fun jobs(): JSONArray {
        val c = URL(server() + "/api/jobs").openConnection() as HttpURLConnection
        c.connectTimeout = 4000; c.readTimeout = 8000
        c.setRequestProperty("X-Token", token())
        if (c.responseCode != 200) throw java.io.IOException("HTTP ${c.responseCode}")
        return JSONArray(c.inputStream.bufferedReader().use { it.readText() })
    }

    private fun enc(s: String) = MainActivity.enc(s)
}
