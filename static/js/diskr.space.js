var $$ = mdui.JQ;
var patSize = /.*\(([0-9]+)\)/;


function status_info(data) {
    for (var k in data) {
        var v = data[k];
        $$("#status tr td[name=" + k + "]").text(v);
    }
}

function update_status() {
    $$("#status tr td[name='files']").text("请稍候...");
    $$.ajax({
        method: "GET",
        url: WEB_PATH + "/status",
        dataType: "json",
        success: function (data, status, xhr) {
            status_info(data);
        }
    });
}

function update_progress() {
    $$.ajax({
        method: "GET",
        url: WEB_PATH + "/scan/progress",
        dataType: "json",
        success: function (data, status, xhr) {
            var progress = parseInt(data["progress"]);
            if (progress < 100) {
                $$("#scan_progress div").width(progress + "%");
                $$("#scan_message").text(data["speed"] + "/s | " + data["cur_path"]);
                // status_info(data['info']);
                setTimeout(update_progress, 1000);
            }
            else {
                $$("#scan_progress").hide();
                $$("#scan_message").text("");
                $$("#scan_now").removeAttr("disabled");
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

function get_wait(tbody, cols, init) {
    var tr = $$("<tr data-toggle='wait'><td colspan='" + cols
        + "' class='mdui-color-theme-50'>等待查询结果...</td></tr>");
    if (init == 0) {
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
        url: WEB_PATH + "/search",
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
    var cmd = $$("#duplicated td.command[data-toggle='" + id + "']");
    cmd.empty();
    cmd.append($$('<div class="mdui-spinner"></div>'));
    cmd.mutation();
    $$.ajax({
        method: "DELETE",
        url: WEB_PATH + "/duplicated/" + id,
        dataType: "json",
        success: function (data, status, xhr) {
            var status = data["status"];
            if (status == "ok") {
                var tr = $$("#duplicated td.command[data-toggle='" + id + "']").parent();
                var fhash = tr.attr("data-toggle");
                var same_hash = $$("#duplicated tr[data-toggle='" + fhash + "']");
                var cls_odd = "mdui-color-theme-50";
                if (same_hash.length == 2) {
                    var trs = $$("#duplicated tbody tr");
                    var flag = 0;
                    $$.each(trs, function (i, v) {
                        v = $$(v);
                        if (flag == 0 && v.attr('data-toggle') == fhash) {
                            flag = 1;
                        }
                        if (flag == 1 && v.attr('data-toggle') != fhash) {
                            flag = 2;
                        }
                        if (flag == 2) {
                            if (v.hasClass(cls_odd)) {
                                v.removeClass(cls_odd);
                            }
                            else {
                                v.addClass(cls_odd);
                            }
                        }
                    });
                    same_hash.remove();
                } else {
                    tr.remove();
                }
                mdui.snackbar({message: "删除成功", position: "top", timeout: 1000});
            } else {
                $$("#duplicated td.command").empty();
                mdui.snackbar({message: "删除失败：" + status, position: "top", timeout: 1000});
            }
        }
    });
}

function update_duplicated(since_size) {
    $$("#refresh_dup").attr("disabled", "1");
    var tbody = $$("#duplicated tbody");
    get_wait(tbody, 5, since_size);
    $$.ajax({
        method: "GET",
        url: WEB_PATH + "/duplicated",
        data: {"since_size": since_size},
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
            var last_size = data[data.length - 1]['size'];
            for (var k in data) {
                var v = data[k];
                var size = v["size"];
                if (size == last_size) {
                    break;
                }
                if (v["ftype"] == "D") {
                    size = "&lt;文件夹&gt;" + v["size"];
                }
                var tr = $$("<tr><td class='selected'><label class='mdui-checkbox'>"
                    + "<input type='checkbox' name='selected_dup' /><i class='mdui-checkbox-icon'></i></label></td><td>"
                    + v["name"] + "</td><td class='mdui-table-col-numeric'>" + size
                    + "</td><td>" + v["ftime"] + "</td><td class='command'></td></tr>");
                tr.children("td.selected").attr("data-toggle", v["id"]);
                tr.children("td.command").attr("data-toggle", v["id"]);
                tr.on("click", function (e) {
                    if ($$("td.command div.mdui-spinner").length > 0) {
                        return;
                    }
                    $$("td.command").empty();
                    var cmd = $$(e.target).parent().children("td.command");
                    var id = cmd.attr("data-toggle");
                    var btn = $$("<button class='mdui-btn mdui-btn-icon mdui-color-theme-100 mdui-ripple'>"
                        + "<i class='mdui-icon material-icons'>delete</i></button>");
                    btn.on("click", dedup_click);
                    btn.attr("data-toggle", id);
                    cmd.append(btn);
                });
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
            if (data.length >= 50) {
                var m = patSize.exec(last_size);
                if (m.length == 2) {
                    since_size = m[1];
                }
                get_more(tbody, 5, parseInt(since_size), update_duplicated);
            }
            $$("#refresh_dup").removeAttr("disabled");
            $$("input[name=selected_dup").on("change", check_selected_dup);
            // $$("#select_top").prop("checked", false);
            // $$("#select_bottom").prop("checked", false);
            if ($$("#select_top").prop("checked")) {
                dup_selected(false);
            }
            else if ($$("#select_bottom").prop("checked")) {
                dup_selected(true);
            }
        }
    });
}

function dup_selected(exclude_first) {  // or exclude last
    var selected_name = "select_top";
    var unselected_name = "select_bottom";
    if (exclude_first) {
        selected_name = "select_bottom";
        unselected_name = "select_top";
    }
    if ($$("#" + selected_name).prop("checked")) {
        $$("#" + unselected_name).prop("checked", false);
        $$("input[name=selected_dup]").prop("checked", true);
        var trs = $$("#duplicated tbody tr");
        var fhash = "";
        $$.each(trs, function (i, v) {
            v = $$(v);
            if (v.attr('data-toggle') != fhash) {
                fhash = v.attr('data-toggle');
                var ck = $$("#duplicated tbody tr[data-toggle='" + fhash + "'] input[name='selected_dup']");
                var idx = ck.length - 1;
                if (exclude_first) {
                    idx = 0;
                }
                $$(ck[idx]).prop("checked", false);
            }
        });
    }
    else {
        $$("input[name=selected_dup]").prop("checked", false);
    }
}

function check_selected_dup(e) {
    var fhash = $$(e.target).parent().parent().parent().attr("data-toggle");
    var cks = $$("#duplicated tbody tr[data-toggle='" + fhash + "'] input[name='selected_dup']");
    var all = true;
    $$.each(cks, function (i, v) {
        v = $$(v);
        if (!v.prop("checked")) {
            all = false;
        }
    });
    if (all) {
        alert("Don't delete all!");
        $$(e.target).prop("checked", false);
    }
}

function delete_selected_items() {
    var selected = $$("input[name='selected_dup']:checked");
    var items = "";
    $$.each(selected, function (i, v) {
        v = $$(v).parent().parent();
        if (items == "") {
            items = v.attr("data-toggle");
        }
        else {
            items += "," + v.attr("data-toggle");
        }
    });
    $$.ajax({
        method: "DELETE",
        url: WEB_PATH + "/duplicated",
        data: {"selected_dup": items},
        dataType: "json",
        success: function (data, status, xhr) {
            var success = data["success"];
            var fail = data["fail"];
            $$.each(success, function (i, v) {
                var tr = $$("#duplicated td.command[data-toggle='" + v + "']").parent();
                var fhash = tr.attr("data-toggle");
                var same_hash = $$("#duplicated tr[data-toggle='" + fhash + "']");
                var cls_odd = "mdui-color-theme-50";
                if (same_hash.length == 2) {
                    var trs = $$("#duplicated tbody tr");
                    var flag = 0;
                    $$.each(trs, function (i, v) {
                        v = $$(v);
                        if (flag == 0 && v.attr('data-toggle') == fhash) {
                            flag = 1;
                        }
                        if (flag == 1 && v.attr('data-toggle') != fhash) {
                            flag = 2;
                        }
                        if (flag == 2) {
                            if (v.hasClass(cls_odd)) {
                                v.removeClass(cls_odd);
                            }
                            else {
                                v.addClass(cls_odd);
                            }
                        }
                    });
                    same_hash.remove();
                } else {
                    tr.remove();
                }
            });
            $$.each(fail, function (i, v) {
                var tr = $$("#duplicated td.command[data-toggle='" + v + "']").parent();
                var cls_odd = "mdui-color-theme-50";
                var cls_fail = "mdui-color-deep-orange-200";
                tr.removeClass(cls_odd);
                tr.addClass(cls_fail);
            });
            mdui.snackbar({message: "删除成功 " + success.length + ", 删除失败 " + fail.length, position: "top",
                timeout: 5000});
            update_duplicated(0);
        }
    });
}

$$(function () {
    update_status();
    update_progress();
    $$("#tab-status").on("show.mdui.tab", function () {
        if ($$("#scan_progress")[0].clientHeight == 0) {
            update_status();
        }
    });
    $$("#scan_now").on("click", function () {
        if ($$("#scan_progress")[0].clientHeight == 0) {
            $$("#scan_progress").show();
            $$("#scan_now").attr("disabled", "1");
            setTimeout(update_progress, 2000);
            $$.ajax({
                method: "POST",
                url: WEB_PATH + "/scan",
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
        if ($$("#duplicated tbody").children().length == 0) {
            update_duplicated(0);
        }
    });
    $$("#select_top").on("change", function () {
        dup_selected(false);
    });
    $$("#select_bottom").on("click", function () {
        dup_selected(true);
    });
    $$("#delete_selected").on("click", delete_selected_items);
    $$("#refresh_dup").on("click", function () {
        update_duplicated(0);
    });
    $$("#tab-settings").on("show.mdui.tab", function () {
        $$.ajax({
            method: "GET",
            url: WEB_PATH + "/settings",
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
            url: WEB_PATH + "/settings",
            data: params,
            dataType: "json",
            success: function (data, status, xhr) {
                if (data['confirm'] == "require") {
                  mdui.dialog({
                      title: 'work_dir changed',
                      content: 'Do you want to delete all old data?',
                      buttons: [
                        {
                          text: 'Cancel'
                        },
                        {
                          text: 'Confirm',
                          onClick: function(e){
                            params['confirm'] = "true";
                            $$.ajax({
                                method: "PUT",
                                url: WEB_PATH + "/settings",
                                data: params,
                                dataType: "json",
                                success: function (data, status, xhr) {
                                    mdui.snackbar({message: "Settings saved", position: "top", timeout: 2000});
                                }
                            });
                          }
                        }
                      ]
                  });
                }
                else {
                    mdui.snackbar({message: "Settings saved", position: "top", timeout: 2000});
                }
            }
        });
    });
})