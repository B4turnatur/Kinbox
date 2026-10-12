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
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.view.View
import android.view.WindowInsets
import android.webkit.JavascriptInterface
import android.webkit.URLUtil
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
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
    private val prefs by lazy { getSharedPreferences("kinbox", MODE_PRIVATE) }
    private val key = UUID.randomUUID().toString()   // nur unsere eigenen Seiten kennen ihn (nicht z. B. der YouTube-Player)
    private var full: View? = null
    private var fullCb: WebChromeClient.CustomViewCallback? = null
    private var fileCb: ValueCallback<Array<Uri>>? = null
    private var polling = false

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        web = WebView(this)
        val root = FrameLayout(this).apply { addView(web) }
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
        web.setDownloadListener { url, _, cd, mime, _ -> download(url, fileName(cd) ?: URLUtil.guessFileName(url, cd, mime)) }
        if (Build.VERSION.SDK_INT >= 33)
            onBackInvokedDispatcher.registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT) { back() }
        open(intent)
        if (tracked().length() > 0) poll()
    }

    override fun onNewIntent(i: Intent) {
        super.onNewIntent(i)
        open(i)
    }

    @Deprecated("bis Android 12")
    override fun onBackPressed() = back()

    private fun back() = when {
        full != null -> (web.webChromeClient as Chrome).onHideCustomView()
        web.canGoBack() -> web.goBack()
        else -> finish()
    }

    // ---- Start: geteilter Link, Einladungslink oder einfach die App ----------

    private fun open(i: Intent) {
        val text = when (i.action) {
            Intent.ACTION_SEND -> i.getStringExtra(Intent.EXTRA_TEXT)
            Intent.ACTION_VIEW -> i.dataString
            else -> null
        } ?: ""
        if (invite(text) != null) { load("popup.html?window=1"); connectAsk(text); return }
        val url = Regex("https?://\\S+").find(text)?.value
        val title = i.getStringExtra(Intent.EXTRA_SUBJECT) ?: ""
        load("popup.html?window=1" + if (url == null) "" else "&tab=1&url=${enc(url)}&title=${enc(title)}")
    }

    private fun load(page: String) {
        val s = server()
        web.loadUrl(if (s.isEmpty()) "$SETUP_ORIGIN/kbapp/setup.html" else "$s/kbapp/$page")
    }

    /** Server + Token aus Einladungslink (…/library?token=…) oder kinbox://setup?server=…&token=… */
    private fun invite(text: String): Pair<String, String>? {
        val u = Regex("(https?|kinbox)://\\S+").find(text)?.value?.let(Uri::parse) ?: return null
        val token = u.getQueryParameter("token")?.takeIf { it.isNotBlank() } ?: return null
        val server = when {
            u.scheme == "kinbox" -> u.getQueryParameter("server")?.takeIf { it.startsWith("http") } ?: return null
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
                saveStore(store().put("serverUrl", server).put("token", token).toString())
                toast(getString(R.string.connected))
                load("popup.html?window=1")
                if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                    requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
            }
            .setNegativeButton(R.string.cancel, null)
            .show()
    }

    // ---- Gespeicherte Einstellungen (entspricht chrome.storage der Erweiterung) ----

    private fun store() = JSONObject(prefs.getString("store", null) ?: "{}")
    private fun saveStore(json: String) = prefs.edit().putString("store", json).apply()

    private fun server(): String {
        val s = store().optString("serverUrl").trim().trimEnd('/')
        return if (s.isEmpty() || s.startsWith("http")) s else "http://$s"
    }

    private fun token() = store().optString("token")

    // ---- Downloads aufs Handy, Benachrichtigungen ------------------------------

    private fun download(url: String, name: String) {
        if (!url.startsWith("http")) return toast(getString(R.string.no_download))
        val file = name.replace(Regex("[\\\\/:*?\"<>|]"), "_")
        val r = DownloadManager.Request(Uri.parse(url))
            .setTitle(file)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "Kinbox/$file")
        getSystemService(DownloadManager::class.java).enqueue(r)
        toast(getString(R.string.saving))
    }

    private fun notify(title: String, text: String) {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("done", getString(R.string.channel), NotificationManager.IMPORTANCE_DEFAULT))
        val tap = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        nm.notify((title + text).hashCode(), Notification.Builder(this, "done")
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle(title).setContentText(text).setContentIntent(tap).setAutoCancel(true).build())
    }

    // Aufträge verfolgen, bis sie fertig sind: dann Benachrichtigung und ggf. aufs Handy laden.
    // ponytail: läuft nur, solange die App offen ist – für „nachts laden" später WorkManager.
    private fun tracked() = JSONObject(prefs.getString("tracked", null) ?: "{}")

    @Synchronized private fun track(id: String, save: Boolean) {
        prefs.edit().putString("tracked", tracked().put(id, save).toString()).apply()
        poll()
    }

    @Synchronized private fun poll() {
        if (polling) return
        polling = true
        thread {
            while (!isDestroyed) {
                try { pollOnce() } catch (_: Exception) { }
                synchronized(this) { if (tracked().length() == 0) { polling = false; return@thread } }
                Thread.sleep(3000)
            }
            polling = false
        }
    }

    private fun pollOnce() {
        val c = URL(server() + "/api/jobs").openConnection() as HttpURLConnection
        c.connectTimeout = 8000; c.readTimeout = 8000
        c.setRequestProperty("X-Token", token())
        val jobs = JSONArray(c.inputStream.bufferedReader().use { it.readText() })
        val notifyOn = store().optBoolean("notify", true)
        synchronized(this) {
            val t = tracked()
            for (i in 0 until jobs.length()) {
                val j = jobs.getJSONObject(i)
                val id = j.optString("id")
                if (!t.has(id)) continue
                val title = j.optString("title")
                when (j.optString("status")) {
                    "finished" -> {
                        if (t.optBoolean(id)) {
                            val files = j.optJSONArray("files") ?: JSONArray()
                            for (f in 0 until files.length()) if (files.getJSONObject(f).optBoolean("exists"))
                                runOnUiThread { download("${server()}/api/jobs/$id/files/$f?token=${enc(token())}", files.getJSONObject(f).optString("name")) }
                        }
                        if (notifyOn) runOnUiThread { notify(getString(R.string.done), title) }
                    }
                    "error" -> if (notifyOn) runOnUiThread { notify(getString(R.string.failed), title) }
                    "cancelled" -> {}
                    else -> continue
                }
                t.remove(id)
            }
            prefs.edit().putString("tracked", t.toString()).apply()
        }
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_LONG).show()

    // ---- Für app.js ------------------------------------------------------------

    inner class Bridge {
        @JavascriptInterface fun load(k: String): String = if (k == key) store().toString() else "{}"
        @JavascriptInterface fun save(k: String, json: String) { if (k == key) saveStore(json) }
        @JavascriptInterface fun download(k: String, url: String, name: String) { if (k == key) runOnUiThread { download(url, name) } }
        @JavascriptInterface fun track(k: String, id: String, save: Boolean) { if (k == key) track(id, save) }
        @JavascriptInterface fun open(k: String, url: String) {
            if (k == key) runOnUiThread { try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) } catch (_: ActivityNotFoundException) { } }
        }
        @JavascriptInterface fun connect(k: String, text: String) { if (k == key) runOnUiThread { connectAsk(text) } }
        @JavascriptInterface fun paste(k: String) {
            if (k == key) runOnUiThread {
                connectAsk(getSystemService(ClipboardManager::class.java).primaryClip?.getItemAt(0)?.coerceToText(this@MainActivity)?.toString() ?: "")
            }
        }
    }

    inner class Client : WebViewClient() {
        override fun shouldInterceptRequest(v: WebView, r: WebResourceRequest): WebResourceResponse? {
            val path = r.url.path ?: return null
            if (!path.startsWith("/kbapp/") || ".." in path) return null
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
            if (u.path?.startsWith("/kbapp/") == true || u.encodedAuthority == Uri.parse(server()).encodedAuthority) return false
            try { startActivity(Intent(Intent.ACTION_VIEW, u)) } catch (_: ActivityNotFoundException) { }
            return true
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
