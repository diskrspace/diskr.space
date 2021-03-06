<!DOCTYPE HTML>
<html lang="zh_CN">
<head>
	<meta charset="UTF-8">
	<title>Diskr.space</title>
    <link rel="shortcut icon" href="{{static_path}}/images/favicon.png"/>
    <link rel="stylesheet" href="{{static_path}}/css/mdui.min.css">
    <link rel="stylesheet" href="{{static_path}}/css/diskr.space.css?v=2">
</head>
<body class="mdui-theme-primary-light-blue">
    <div class="mdui-container-fluid">
        <div class="mdui-appbar mdui-appbar-scroll-hide">
            <div class="mdui-toolbar">
                <div><a href="/"><img src="{{static_path}}/images/logo.png" border="0" class="mdui-img-fluid"/></a></div>
                <div class="mdui-toolbar-spacer"></div>
                <div>V 1.0a8</div>
            </div>
            <div class="mdui-tab mdui-color-light-blue-100" mdui-tab>
                <a id="tab-status" href="#ds-status" class="mdui-ripple">Status</a>
                <a id="tab-search" href="#ds-search" class="mdui-ripple">Search</a>
                <a id="tab-duplicated" href="#ds-duplicated" class="mdui-ripple">Duplicated</a>
                <a id="tab-settings" href="#ds-settings" class="mdui-ripple">Settings</a>
            </div>
        </div>
        <div id="ds-status" class="mdui-p-a-2 mdui-color-light-blue-50 dsbox-page">
            <h2>Status</h2>
            <div class="mdui-table-fluid">
                <div class="mdui-progress" id="scan_progress">
                  <div class="mdui-progress-determinate" style="width: 0%;"></div>
                </div>
                <div class="mdui-toolbar mdui-color-light-blue-50">
                    <div id="scan_message"></div>
                    <div class="mdui-toolbar-spacer"></div>
                    <button id="scan_now" class="mdui-btn mdui-ripple mdui-color-light-blue-200">Scan now</button>
                </div>
                <table id="status" class="mdui-table">
                    <thead>
                    <tr class="mdui-color-theme-100">
                        <th>Directory</th>
                        <th class="mdui-table-col-numeric">Directories</th>
                        <th class="mdui-table-col-numeric">Files</th>
                        <th class="mdui-table-col-numeric">Total size</th>
                        <th>Last modified</th>
                    </tr>
                    </thead>
                    <tbody>
                    <tr>
                        <td name="work_dir"></td>
                        <td class="mdui-table-col-numeric" name="dirs"></td>
                        <td class="mdui-table-col-numeric" name="files"></td>
                        <td class="mdui-table-col-numeric" name="size"></td>
                        <td name="updated"></td>
                    </tr>
                    </tbody>
                </table>
            </div>
        </div>
        <div id="ds-search" class="mdui-p-a-2 mdui-color-light-blue-50 dsbox-page">
            <h2>Search</h2>
            <div class="mdui-table-fluid">
                <div class="mdui-toolbar mdui-color-light-blue-50">
                    <div class="mdui-toolbar-spacer"></div>
                    <div class="mdui-textfield">
                      <input class="mdui-textfield-input" type="text" placeholder="Tags" id="search_tags"/>
                    </div>
                    <button id="search_now" class="mdui-btn mdui-ripple mdui-color-light-blue-200">Search</button>
                </div>
                <table id="search" class="mdui-table">
                    <thead>
                    <tr class="mdui-color-theme-100">
                        <th>Fullname</th>
                        <th class="mdui-table-col-numeric">Size</th>
                        <th>Last modified</th>
                    </tr>
                    </thead>
                    <tbody>
                    </tbody>
                </table>
            </div>
        </div>
        <div id="ds-duplicated" class="mdui-p-a-2 mdui-color-light-blue-50 dsbox-page">
            <h2>Duplicatied</h2>
            <div class="mdui-table-fluid">
                <div class="mdui-toolbar mdui-color-light-blue-50">
                    <label class="mdui-checkbox">
                        <input type="checkbox" id="select_top"/><i class="mdui-checkbox-icon"></i>Select all dup(exclude last one)
                    </label>
                    <label class="mdui-checkbox">
                        <input type="checkbox" id="select_bottom"/><i class="mdui-checkbox-icon"></i>Select all dup(exclude first one)
                    </label>
                    <button id="delete_selected" class="mdui-btn mdui-ripple mdui-color-light-blue-200">Delete selected</button>
                    <div class="mdui-toolbar-spacer"></div>
                    <button id="refresh_dup" class="mdui-btn mdui-ripple mdui-color-light-blue-200">Refresh</button>
                </div>
                <table id="duplicated" class="mdui-table">
                    <thead>
                    <tr class="mdui-color-theme-100">
                        <th>Selected</th>
                        <th>Fullname</th>
                        <th class="mdui-table-col-numeric">Size</th>
                        <th>Last modified</th>
                        <th>Delete</th>
                    </tr>
                    </thead>
                    <tbody>
                    </tbody>
                </table>
            </div>
        </div>
        <div id="ds-settings" class="mdui-p-a-2 mdui-color-light-blue-50 dsbox-page">
            <h2>Settings</h2>
            <div class="mdui-table-fluid">
                <div class="mdui-toolbar mdui-color-light-blue-50">
                  <div class="mdui-toolbar-spacer"></div>
                  <button id="apply_config" class="mdui-btn mdui-ripple mdui-color-light-blue-200">Apply</button>
                </div>
                <table id="config" class="mdui-table">
                    <thead>
                    <tr class="mdui-color-theme-100">
                        <th>Setting</th>
                        <th>Value</th>
                        <th>Default</th>
                        <th>Comment</th>
                    </tr>
                    </thead>
                    <tbody>
                    <tr>
                        <td>Directory</td>
                        <td><input name="work_dir" /></td>
                        <td>~/</td>
                        <td>默认扫描目录</td>
                    </tr>
                    <tr>
                        <td>Quick hash size</td>
                        <td><input name="quick_hash_size" /></td>
                        <td>0</td>
                        <td>快速HASH块大小，为0时做全文件HASH，可用K，M，G为单位</td>
                    </tr>
                    <tr>
                        <td>Scan interval</td>
                        <td><input name="scan_interval" /></td>
                        <td>86400</td>
                        <td>扫描间隔时间，单位为秒</td>
                    </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
<div class="mdui-dialog">
  <div class="mdui-dialog-title">work_dir changed</div>
  <div class="mdui-dialog-content">Do you want to delete all old data?</div>
  <div class="mdui-dialog-actions">
    <button class="mdui-btn mdui-ripple">Yes</button>
    <button class="mdui-btn mdui-ripple">No</button>
  </div>
</div>
    <footer>
        <p>Copyright &copy; 2018 by <a href="//diskr.space/">Diskr.space .</a></p>
        <div>Icons made by <a href="https://www.flaticon.com/authors/smashicons" title="Smashicons">Smashicons</a>
            from <a href="https://www.flaticon.com/" title="Flaticon">www.flaticon.com</a>
            is licensed by <a href="http://creativecommons.org/licenses/by/3.0/" title="Creative Commons BY 3.0" target="_blank">
                CC 3.0 BY</a></div>
    </footer>
    <script type="text/javascript">
    var WEB_PATH="{{web_path}}";
    </script>
    <script type="text/javascript" src="{{static_path}}/js/mdui.min.js"></script>
    <script type="text/javascript" src="{{static_path}}/js/diskr.space.js?v=8"></script>
</body>
</html>
