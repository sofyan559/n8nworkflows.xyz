<?php
/**
 * Plugin Name: Engineering Geniuses n8n Workflow Library
 * Description: Searchable n8n workflow library with real validated WEBP previews.
 * Version: 1.0.3
 * Author: Engineering Geniuses
 */

if (!defined('ABSPATH')) exit;

final class EG_N8N_Workflow_Library_103 {
    const VERSION = '1.0.3';
    const OWNER = 'sofyan559';
    const REPO = 'n8nworkflows.xyz';
    const BRANCH = 'main';

    public static function init() {
        add_shortcode('eg_n8n_workflows', [__CLASS__, 'shortcode']);
        add_action('wp_ajax_eg_n8n_asset', [__CLASS__, 'asset_proxy']);
        add_action('wp_ajax_nopriv_eg_n8n_asset', [__CLASS__, 'asset_proxy']);
    }

    private static function safe_part($value) {
        $value = rawurldecode((string) $value);
        $value = str_replace(["\0", "\\"], ['', '/'], $value);
        if ($value === '' || strpos($value, '..') !== false || $value[0] === '/') return false;
        return $value;
    }

    private static function remote_sources($folder, $file) {
        $rel = 'workflows/' . $folder . '/' . $file;
        $encoded = implode('/', array_map('rawurlencode', explode('/', $rel)));
        return [
            'https://raw.githubusercontent.com/' . self::OWNER . '/' . self::REPO . '/' . self::BRANCH . '/' . $encoded,
            'https://cdn.jsdelivr.net/gh/' . self::OWNER . '/' . self::REPO . '@' . self::BRANCH . '/' . $encoded,
        ];
    }

    private static function get_remote($urls, $timeout = 12) {
        foreach ($urls as $url) {
            $r = wp_remote_get($url, [
                'timeout' => $timeout,
                'redirection' => 3,
                'headers' => ['User-Agent' => 'Engineering-Geniuses-n8n-Library/' . self::VERSION],
            ]);
            if (!is_wp_error($r) && wp_remote_retrieve_response_code($r) === 200) {
                return wp_remote_retrieve_body($r);
            }
        }
        return false;
    }

    private static function valid_image($bytes, $ext) {
        if (!$bytes) return false;
        $ext = strtolower($ext);
        if ($ext === 'webp') return strlen($bytes) >= 12 && substr($bytes, 0, 4) === 'RIFF' && substr($bytes, 8, 4) === 'WEBP';
        if ($ext === 'png') return substr($bytes, 0, 8) === "\x89PNG\r\n\x1a\n";
        if ($ext === 'jpg' || $ext === 'jpeg') return substr($bytes, 0, 3) === "\xFF\xD8\xFF";
        if ($ext === 'gif') return in_array(substr($bytes, 0, 6), ['GIF87a', 'GIF89a'], true);
        return false;
    }

    public static function asset_proxy() {
        $kind = isset($_GET['kind']) ? sanitize_key(wp_unslash($_GET['kind'])) : '';
        $folder = isset($_GET['folder']) ? self::safe_part(wp_unslash($_GET['folder'])) : false;
        $file = isset($_GET['file']) ? self::safe_part(wp_unslash($_GET['file'])) : false;
        if (!$folder || !$file || !in_array($kind, ['image', 'text'], true)) {
            status_header(400); exit;
        }

        $ext = strtolower(pathinfo($file, PATHINFO_EXTENSION));
        if ($kind === 'image' && !in_array($ext, ['webp','png','jpg','jpeg','gif'], true)) { status_header(400); exit; }
        if ($kind === 'text' && !in_array($ext, ['json','md','txt'], true)) { status_header(400); exit; }

        $cache = wp_upload_dir();
        $dir = trailingslashit($cache['basedir']) . 'eg-n8n-workflow-cache';
        if (!is_dir($dir)) wp_mkdir_p($dir);
        $cache_file = trailingslashit($dir) . sha1($kind . '|' . $folder . '|' . $file) . '.' . $ext;

        if (is_file($cache_file) && filesize($cache_file) > 0) {
            $body = file_get_contents($cache_file);
        } else {
            $body = self::get_remote(self::remote_sources($folder, $file));
            if ($body === false) { status_header(404); exit; }
            if ($kind === 'image' && !self::valid_image($body, $ext)) { status_header(404); exit; }
            @file_put_contents($cache_file, $body, LOCK_EX);
        }

        if ($kind === 'image') {
            $mimes = ['webp'=>'image/webp','png'=>'image/png','jpg'=>'image/jpeg','jpeg'=>'image/jpeg','gif'=>'image/gif'];
            header('Content-Type: ' . $mimes[$ext]);
            header('Cache-Control: public, max-age=604800');
        } else {
            header('Content-Type: text/plain; charset=utf-8');
            header('Cache-Control: public, max-age=3600');
        }
        echo $body;
        exit;
    }

    public static function shortcode() {
        $base = plugin_dir_url(__FILE__);
        wp_enqueue_style('eg-n8n-workflow-library', $base . 'assets/style.css', [], self::VERSION);
        wp_enqueue_script('eg-n8n-workflow-library', $base . 'assets/app.js', [], self::VERSION, true);
        wp_localize_script('eg-n8n-workflow-library', 'EGN8N', [
            'catalogUrl' => $base . 'catalog.json',
            'ajaxUrl' => admin_url('admin-ajax.php'),
            'rawBase' => 'https://raw.githubusercontent.com/' . self::OWNER . '/' . self::REPO . '/' . self::BRANCH . '/',
            'cdnBase' => 'https://cdn.jsdelivr.net/gh/' . self::OWNER . '/' . self::REPO . '@' . self::BRANCH . '/',
        ]);

        ob_start(); ?>
<div id="eg-n8n-app" class="egn-app">
  <section class="egn-hero">
    <div><span class="egn-kicker">Automation workflow library</span><h1>Find the workflow you need.</h1><p>Search ready-to-import n8n workflows, preview the real workflow screenshots, inspect details, and download the JSON.</p></div>
    <div class="egn-total"><strong id="egn-total">—</strong><span>workflows available</span></div>
    <div class="egn-toolbar">
      <label class="egn-search"><span>⌕</span><input id="egn-search" type="search" placeholder="Search Telegram, Odoo, Gmail, AI agent, invoice..." autocomplete="off"></label>
      <select id="egn-sort"><option value="preview-id-desc">Previews first</option><option value="id-desc">Newest first</option><option value="title-asc">Name A–Z</option><option value="title-desc">Name Z–A</option></select>
      <button id="egn-clear" type="button">Clear</button>
    </div>
  </section>
  <div class="egn-layout">
    <aside class="egn-sidebar"><h3>Categories</h3><div id="egn-categories"></div></aside>
    <main class="egn-main"><select id="egn-mobile-category" class="egn-mobile-category"></select><div id="egn-results" class="egn-results">Loading local catalog…</div><div id="egn-list"><div class="egn-loading"><i></i>Loading workflow catalog…</div></div><div id="egn-pages" class="egn-pages"></div></main>
  </div>
</div>
<div id="egn-modal" class="egn-modal"><div class="egn-panel"><div class="egn-panelbar"><div><button id="egn-download" class="egn-primary">↓ Download Workflow</button><button id="egn-copy">Copy JSON</button><a id="egn-n8n" href="#" target="_blank" rel="noopener" style="display:none">View on n8n.io ↗</a></div><button id="egn-close" class="egn-close">×</button></div><div id="egn-modalbody" class="egn-modalbody"></div></div></div><div id="egn-toast" class="egn-toast"></div>
<?php return ob_get_clean();
    }
}
EG_N8N_Workflow_Library_103::init();
