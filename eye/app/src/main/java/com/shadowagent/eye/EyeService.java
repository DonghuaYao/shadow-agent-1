package com.shadowagent.eye;

import android.accessibilityservice.AccessibilityService;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Rect;
import android.util.Log;
import android.util.SparseArray;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * 只做一件事：收到 DUMP 广播后，把所有屏幕上所有窗口的界面树写成一个 xml 文件。
 * 读窗口用的是无障碍接口，不需要像 uiautomator 那样等界面“空闲”。
 */
public class EyeService extends AccessibilityService {

    private static final String TAG = "ShadowEye";
    private static final String ACTION_DUMP = "com.shadowagent.eye.DUMP";
    private static final int MAX_DEPTH = 40;
    private static final int MAX_NODES = 2000;

    private final BroadcastReceiver receiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String id = intent.getStringExtra("id");
            writeDump(id == null ? "0" : id, intent.getStringExtra("display"));
        }
    };

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        registerReceiver(receiver, new IntentFilter(ACTION_DUMP), Context.RECEIVER_EXPORTED);
        Log.i(TAG, "service connected, waiting for " + ACTION_DUMP);
    }

    @Override
    public void onDestroy() {
        try {
            unregisterReceiver(receiver);
        } catch (Exception ignored) {
        }
        super.onDestroy();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }

    private void writeDump(String requestId, String onlyDisplay) {
        long start = System.currentTimeMillis();
        StringBuilder sb = new StringBuilder(64 * 1024);
        sb.append("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\" ?>");
        sb.append("<displays req=\"").append(esc(requestId)).append("\">");

        int[] count = new int[]{0};
        SparseArray<List<AccessibilityWindowInfo>> all = getWindowsOnAllDisplays();
        for (int i = 0; i < all.size(); i++) {
            if (onlyDisplay != null && !onlyDisplay.equals(String.valueOf(all.keyAt(i)))) {
                continue;
            }
            sb.append("<display id=\"").append(all.keyAt(i)).append("\">");
            for (AccessibilityWindowInfo window : all.valueAt(i)) {
                appendWindow(sb, window, count);
            }
            sb.append("</display>");
        }
        sb.append("</displays>");

        try {
            File dir = getFilesDir();
            File tmp = new File(dir, "ui.xml.tmp");
            File out = new File(dir, "ui.xml");
            try (FileOutputStream fos = new FileOutputStream(tmp)) {
                fos.write(sb.toString().getBytes(StandardCharsets.UTF_8));
            }
            // 先写临时文件再改名，读的一方不会读到写了一半的内容
            if (!tmp.renameTo(out)) {
                Log.e(TAG, "rename failed");
            }
        } catch (Exception e) {
            Log.e(TAG, "write failed: " + e);
        }
        Log.i(TAG, "dump req=" + requestId + " nodes=" + count[0]
                + " ms=" + (System.currentTimeMillis() - start));
    }

    private void appendWindow(StringBuilder sb, AccessibilityWindowInfo window, int[] count) {
        sb.append("<window type=\"").append(typeName(window.getType()))
                .append("\" layer=\"").append(window.getLayer()).append("\">");
        AccessibilityNodeInfo root = window.getRoot();
        if (root != null) {
            appendNode(sb, root, 0, count);
        }
        sb.append("</window>");
    }

    private void appendNode(StringBuilder sb, AccessibilityNodeInfo n, int depth, int[] count) {
        if (n == null || depth > MAX_DEPTH || count[0] >= MAX_NODES) {
            return;
        }
        count[0]++;

        Rect r = new Rect();
        n.getBoundsInScreen(r);

        sb.append("<node");
        attr(sb, "text", esc(n.getText()));
        attr(sb, "resource-id", esc(n.getViewIdResourceName()));
        attr(sb, "class", esc(n.getClassName()));
        attr(sb, "package", esc(n.getPackageName()));
        attr(sb, "content-desc", esc(n.getContentDescription()));
        attr(sb, "checkable", String.valueOf(n.isCheckable()));
        attr(sb, "checked", String.valueOf(n.isChecked()));
        attr(sb, "clickable", String.valueOf(n.isClickable()));
        attr(sb, "enabled", String.valueOf(n.isEnabled()));
        attr(sb, "focusable", String.valueOf(n.isFocusable()));
        attr(sb, "focused", String.valueOf(n.isFocused()));
        attr(sb, "long-clickable", String.valueOf(n.isLongClickable()));
        attr(sb, "scrollable", String.valueOf(n.isScrollable()));
        attr(sb, "password", String.valueOf(n.isPassword()));
        attr(sb, "selected", String.valueOf(n.isSelected()));
        attr(sb, "bounds", "[" + r.left + "," + r.top + "][" + r.right + "," + r.bottom + "]");
        sb.append(">");

        int children = n.getChildCount();
        for (int i = 0; i < children; i++) {
            AccessibilityNodeInfo child = n.getChild(i);
            if (child != null) {
                appendNode(sb, child, depth + 1, count);
            }
        }
        sb.append("</node>");
    }

    private static void attr(StringBuilder sb, String name, String value) {
        sb.append(' ').append(name).append("=\"").append(value).append('"');
    }

    private static String typeName(int type) {
        switch (type) {
            case AccessibilityWindowInfo.TYPE_APPLICATION:
                return "application";
            case AccessibilityWindowInfo.TYPE_INPUT_METHOD:
                return "input_method";
            case AccessibilityWindowInfo.TYPE_SYSTEM:
                return "system";
            case AccessibilityWindowInfo.TYPE_ACCESSIBILITY_OVERLAY:
                return "overlay";
            default:
                return "other";
        }
    }

    /** 转义 xml 特殊字符，去掉不合法的控制字符，过长的文字截断 */
    private static String esc(CharSequence s) {
        if (s == null) {
            return "";
        }
        String t = s.toString();
        if (t.length() > 200) {
            t = t.substring(0, 200);
        }
        StringBuilder o = new StringBuilder(t.length() + 8);
        for (int i = 0; i < t.length(); i++) {
            char ch = t.charAt(i);
            if (ch == '&') {
                o.append("&amp;");
            } else if (ch == '<') {
                o.append("&lt;");
            } else if (ch == '>') {
                o.append("&gt;");
            } else if (ch == '"') {
                o.append("&quot;");
            } else if (ch < 0x20) {
                o.append(' ');
            } else {
                o.append(ch);
            }
        }
        return o.toString();
    }
}