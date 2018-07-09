var $$ = mdui.JQ;

function update_status() {
    $$("#status tr td[name='files']").text("请稍候...");
    $$.ajax({
        method: "GET",
        url: "status",
        dataType: "json",
        success: function (data, status, xhr) {
            for (var k in data) {
                var v = data[k];
                $$("#status tr td[name=" + k + "]").text(v);
            }
        }
    });
}

function update_progress() {
    $$.ajax({
        method: "GET",
        url: "scan/progress",
        dataType: "json",
        success: function (data, status, xhr) {
            var progress = parseInt(data["progress"]);
            if (progress < 100) {
                $$("#scan_progress div").width(progress + "%");
                $$("#scan_message").text(data["speed"] + "/s | " + data["cur_path"]);
                setTimeout(update_progress, 1000);
            }
            else {
                $$("#scan_progress").hide();
                $$("#scan_message").text("");
                update_status();
            }
        }
    });
}

function get_more(tbody, cols, page, fn) {
    var tr = $$("<tr data-toggle='more'><td colspan='" + cols
        + "' class='mdui-color-theme-50'><button data-toggle='" + page
        + "' class='mdui-btn mdui-color-theme-50 mdui-ripple mdui-center' style='width: 100%'>加载更多</button></td></tr>");
    tr.on("click", function (e) {
        var page = $$(e.target).attr("data-toggle");
        fn(page);
    });
    tbody.append(tr);
}

function get_wait(tbody, cols, page) {
    var tr = $$("<tr data-toggle='wait'><td colspan='" + cols
        + "' class='mdui-color-theme-50'>等待查询结果...</td></tr>");
    if (page == 0) {
        tbody.empty();
    } else {
        tbody.find("tr[data-toggle='more']").remove();
    }
    tbody.append(tr);
}

function update_search(page) {
    var tags = $$("#search_tags").val().trim();
    if (tags=="") {
        mdui.snackbar({message: "请输入搜索标签", position: "top", timeout: 10000});
        return;
    }
    var tbody = $$("#search tbody");
    get_wait(tbody, 3, page);
    $$.ajax({
        method: "GET",
        url: "search",
        data: {"tags": tags, "page": page},
        dataType: "json",
        success: function (data, status, xhr) {
            tbody.find("tr[data-toggle='wait']").remove();
            data = data["searchfiles"];
            for (var k in data) {
                var v = data[k];
                var size = v["size"];
                if (v["ftype"] == "D") {
                    size = "&lt;文件夹&gt;" + v["size"];
                }
                var tr = $$("<tr><td>" + v["name"] + "</td><td class='mdui-table-col-numeric'>" + size
                    + "</td><td>" + v["ftime"] + "</td></tr>");
                tbody.append(tr);
            }
            if (data.length == 50) {
                get_more(tbody, 3, parseInt(page) + 1, update_search);
            }
        }
    });
}

function dedup_click(e) {
    var id = $$(e.target).parent().attr("data-toggle");
    $$.ajax({
        method: "DELETE",
        url: "duplicated/" + id,
        dataType: "json",
        success: function (data, status, xhr) {
            var status = data["status"];
            if (status == "ok") {
                var tr = $$("#duplicated button[data-toggle='" + id + "']").parent().parent();
                var fhash = tr.attr("data-toggle");
                var same_hash = $$("#duplicated tr[data-toggle='" + fhash + "']");
                if (same_hash.length == 2) {
                    same_hash.remove();
                } else {
                    tr.remove();
                }
                mdui.snackbar({message: "删除成功", position: "top", timeout: 1000});
            } else {
                mdui.snackbar({message: "删除失败：" + status, position: "top", timeout: 1000});
            }
        }
    });
}

function update_duplicated(page) {
    var tbody = $$("#duplicated tbody");
    get_wait(tbody, 4, page);
    $$.ajax({
        method: "GET",
        url: "duplicated",
        data: {"page": page},
        dataType: "json",
        success: function (data, status, xhr) {
            tbody.find("tr[data-toggle='wait']").remove();
            data = data["dupfiles"];
            var tr = tbody.find("tr:not([data-toggle='more']):last-child");
            var prev_hash = tr.attr("data-toggle");
            var cls_odd = "mdui-color-theme-50";
            var cls = "";
            if (tr.hasClass(cls_odd)) {
                cls = cls_odd;
            }
            for (var k in data) {
                var v = data[k];
                var size = v["size"];
                if (v["ftype"] == "D") {
                    size = "&lt;文件夹&gt;" + v["size"];
                }
                var btn = $$("<button class='mdui-btn mdui-btn-icon mdui-color-theme-100 mdui-ripple'>"
                    + "<i class='mdui-icon material-icons'>delete</i></button>");
                btn.attr("data-toggle", v["id"]);
                btn.on("click", dedup_click);
                var tr = $$("<tr><td>" + v["name"] + "</td><td class='mdui-table-col-numeric'>" + size
                    + "</td><td>" + v["ftime"] + "</td><td></td></tr>");
                $$(tr.children()[3]).append(btn);
                tr.attr("data-toggle", v["fhash"]);
                if (v["fhash"] != prev_hash) {
                    prev_hash = v["fhash"];
                    if (cls == "") {
                        cls = cls_odd;
                    } else {
                        cls = "";
                    }
                }
                if (cls != "") {
                    tr.addClass(cls);
                }
                tbody.append(tr);
            }
            if (data.length == 50) {
                get_more(tbody, 4, parseInt(page) + 1, update_duplicated);
            }
        }
    });
}

$$(function () {
    update_status();
    update_progress();
    $$("#tab-status").on("show.mdui.tab", function () {
        update_status();
    });
    $$("#scan_now").on("click", function () {
        if ($$("#scan_progress")[0].clientHeight == 0) {
            $$("#scan_progress").show();
            update_progress();
            $$.ajax({
                method: "POST",
                url: "scan",
                dataType: "json",
                success: function (data, status, xhr) {
                    mdui.snackbar({message: data['message'], position: "top", timeout: 1000});
                }
            });
        }
    });
    $$("#search_now").on("click", function () {
        update_search(0);
    });
    $$("#tab-duplicated").on("show.mdui.tab", function () {
        update_duplicated(0);
    });
    $$("#tab-settings").on("show.mdui.tab", function () {
        $$.ajax({
            method: "GET",
            url: "settings",
            dataType: "json",
            success: function (data, status, xhr) {
                for (var k in data) {
                    var v = data[k];
                    $$("#config input[name=" + k + "]").val(v);
                }
            }
        });
    });
    $$("#apply_config").on("click", function () {
        var inputs = $$("#config input");
        var params = {};
        $$.each(inputs, function (i, v) {
            params[v.name] = v.value;
        });
        $$.ajax({
            method: "PUT",
            url: "settings",
            data: params,
            dataType: "json",
            success: function (data, status, xhr) {
                mdui.snackbar({message: "Settings saved", position: "top", timeout: 2000});
            }
        });
    });
})