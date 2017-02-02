/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

"use strict";

const { classes: Cc, interfaces: Ci, utils: Cu, results: Cr } = Components;

const DEFAULT_TIMEOUT = 10000;

Cu.import("resource://gre/modules/Services.jsm");
Cu.import("resource://gre/modules/XPCOMUtils.jsm");
Cu.import("resource://gre/modules/NetUtil.jsm");


// // Register resource://app/ URI
// let ios = Cc["@mozilla.org/network/io-service;1"].getService(Ci.nsIIOService);
// let resHandler = ios.getProtocolHandler("resource").QueryInterface(Ci.nsIResProtocolHandler);
// let mozDir = Cc["@mozilla.org/file/directory_service;1"].getService(Ci.nsIProperties).get("CurProcD", Ci.nsILocalFile);
// let mozDirURI = ios.newFileURI(mozDir);
// resHandler.setSubstitution("app", mozDirURI);

// // let greDir = Cc["@mozilla.org/file/directory_service;1"].getService(Ci.nsIProperties).get("GreBinD", Ci.nsILocalFile);
// let greDir = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsILocalFile);
// let greDirURI = ios.newFileURI(greDir);
// //let greDirURI = ios.newURI("resource://devtools/", null, null);
// resHandler.setSubstitution("devtools", greDirURI);
//
//
//
//
// let homeDir = Cc["@mozilla.org/file/directory_service;1"].getService(Ci.nsIProperties).get("Home", Ci.nsILocalFile);
// let homeDirURI = ios.newFileURI(homeDir);
// dump(resHandler.resolveURI(homeDirURI) + "\n");
//
// let devtoolsURI = ios.newURI("jar:file:///Applications/FirefoxNightly.app/Contents/Resources/omni.ja!/modules/", null, null);
// dump(resHandler.resolveURI(devtoolsURI) + "\n");
//
// dump(resHandler.resolveURI(ios.newURI("resource://gre/modules/Services.jsm", null, null)) + "\n");
// dump(resHandler.resolveURI(ios.newURI("resource://devtools/shared/event-emitter.js", null, null)) + "\n");


// const {EventEmitter} = Cu.import("resource://devtools/shared/event-emitter.js", {});
// Cu.import("resource://devtools/client/framework/gDevTools.jsm");


// Components.utils.import("resource://gre/modules/AppConstants.jsm");
//
// function set_prefs() {
//     Services.prefs.setBoolPref("services.blocklist.signing.enforced", false);
// }
//
// print(Services.prefs.getBoolPref("services.blocklist.signing.enforced"));
// set_prefs();
// print(Services.prefs.getBoolPref("services.blocklist.signing.enforced"));
// use_profile("/tmp/test_profile2");
// print(Services.prefs.getBoolPref("services.blocklist.signing.enforced"));
// set_prefs();
// print(Services.prefs.getBoolPref("services.blocklist.signing.enforced"));


// function create_profile(rootPath, profileName) {
//     let ps = Cc["@mozilla.org/toolkit/profile-service;1"]
//         .getService(Ci.nsIToolkitProfileService);
//     // let ps = Cc["@mozilla.org/toolkit/profile-service;1"]
//     //     .createInstance(Ci.nsIToolkitProfileService);
//     let rootDir = ios.newURI("file://" + rootPath, null, null);
//     ps.createProfile(rootDir, profileName);
// }

// create_profile("/tmp/profiles", "_testtest");

// test profile stuff
// WIP:
// * add logic back in
// * clean up variable names
// * remove hard-coded profile and make dynamic profile path


function use_profile(profd) {
    let file = Cc["@mozilla.org/file/local;1"].createInstance(Ci.nsILocalFile);
    file.initWithPath(profd);
    let provider = {
        getFile: function (prop, persistent) {
            //dump ( "prop: " + prop + "\n");
            persistent.value = true;
            if (prop == "ProfD" || prop == "ProfLD" || prop == "ProfDS" ||
                prop == "ProfLDS" || prop == "PrefD" || prop == "TmpD") {
                return file.clone();
            }
            return null;
        },
        QueryInterface: function (iid) {
            if (iid.equals(Ci.nsIDirectoryServiceProvider) ||
                iid.equals(Ci.nsISupports)) {
                return this;
            }
            throw Cr.NS_ERROR_NO_INTERFACE;
        }
    };
    Cc["@mozilla.org/file/directory_service;1"].getService(Ci.nsIProperties)
        .QueryInterface(Ci.nsIDirectoryService).registerProvider(provider);

    // The methods of 'provider' will retain this scope so null out everything
    // to avoid spurious leak reports.
    profd = null;
    provider = null;

    return file.clone();
}

function update_profile() {
    Cc["@mozilla.org/extensions/blocklist;1"].getService(Ci.nsITimerCallback).notify(null);
}


// Respect async processing
let gScriptDone = false;
let gThreadManager = Cc["@mozilla.org/thread-manager;1"].getService(Ci.nsIThreadManager);
let mainThread = gThreadManager.mainThread;

function scan_url(url) {

    let scan_url_promise = function _scan_url_promise(resolve, reject) {

        const { classes: Cc, interfaces: Ci, utils: Cu, results: Cr } = Components;

        function analyze_security_info(xhr) {
            return {};
            // print("in analyze_security_info");
            let sec_info = xhr.channel.securityInfo;
            if (sec_info instanceof Ci.nsITransportSecurityInfo)
                sec_info.QueryInterface(Ci.nsITransportSecurityInfo);
            // print("in analyze_security_info2");
            let raw_error = sec_info.errorMessage;
            let cert_chain = [];
            // print("in analyze_security_info3");
            if (sec_info instanceof Ci.nsISSLStatusProvider) {
                // print("in analyze_security_info4");
                if (sec_info.QueryInterface(Ci.nsISSLStatusProvider).SSLStatus != null) {
                    // print("in analyze_security_info5");
                    let status = sec_info.QueryInterface(Ci.nsISSLStatusProvider).SSLStatus.QueryInterface(Ci.nsISSLStatus);
                    // print("in analyze_security_info6");
                    let cert = status.serverCert;
                    // print("in analyze_security_info7");
                    if (cert.sha1Fingerprint) {
                        // print("in analyze_security_info8");
                        let l = {};
                        // print("in analyze_security_info9");
                        cert_chain.push(cert.getRawDER(l));
                        let chain = cert.getChain().enumerate();
                        while (chain.hasMoreElements()) {
                            // print("in analyze_security_info10");
                            let childCert = chain.getNext().QueryInterface(Ci.nsISupports).QueryInterface(Ci.nsIX509Cert);
                            let l = {};
                            // print("in analyze_security_info11");
                            cert_chain.push(childCert.getRawDER(l));
                            // print("in analyze_security_info12");
                        }
                    }
                }
            }
            // print("end of analyze_security_info" + JSON.stringify(cert_chain));
            return {chain: cert_chain, error: raw_error};
        }

        function load_handler(msg) {
            // print("in load handler: " + JSON.stringify(msg));

            if (msg.target.readyState === 4) {
                // clearTimeout();
                // completed(null, e.target); // no error
                resolve({result: msg, info: analyze_security_info(msg.target)});
            } else {
                reject({error: msg, info: analyze_security_info(msg.target)});
            }
        }

        function error_handler(msg) {
            // print("in error handler: " + JSON.stringify(msg));
            // completed(e.target.channel.QueryInterface(Ci.nsIRequest).status, e.target);
            reject({error: msg, info: analyze_security_info(msg.target)});
        }

        function timeout_handler(msg) {
            // print("in timeout handler: " + JSON.stringify(msg));
            // completed(e.target.channel.QueryInterface(Ci.nsIRequest).status, e.target);
            reject({error: msg, info: analyze_security_info(msg.target)});
        }

        function RedirectStopper() {
        }

        RedirectStopper.prototype = {
            // nsIChannelEventSink
            asyncOnChannelRedirect: function (oldChannel, newChannel, flags, callback) {
                throw Cr.NS_ERROR_ENTITY_CHANGED;
            },
            getInterface: function (iid) {
                return this.QueryInterface(iid);
            },
            QueryInterface: XPCOMUtils.generateQI([Ci.nsIChannelEventSink])
        };

        // print("in scan_url promise: " + JSON.stringify(req));

        let req = Cc["@mozilla.org/xmlextras/xmlhttprequest;1"].createInstance(Ci.nsIXMLHttpRequest);
        try {
            req.open("HEAD", "https://" + url, true);
            req.timeout = DEFAULT_TIMEOUT;
            req.channel.notificationCallbacks = new RedirectStopper();
            req.addEventListener("load", load_handler, false);
            req.addEventListener("error", error_handler, false);
            req.addEventListener("timeout", timeout_handler, false);
            req.send();
        } catch (error) {
            // print("scan_url error caught: " + JSON.stringify(error));
            reject({error: error, info: analyze_security_info(req)});
        }
        // print("end of scan_url promise");
    };

    return new Promise(scan_url_promise.bind(this)); //.bind(this));  // Without the bind, JSON etc aren't available inside the promise environment.
}

function get_runtime_info() {
//    Cu.import("resource://gre/modules/Services.jsm");
//    Cu.import("resource://gre/modules/FileUtils.jsm");
//    Cu.import("resource://gre/modules/XPCOMUtils.jsm");
//    Cu.import("resource://gre/modules/NetUtil.jsm");
    Cu.import("resource://gre/modules/AppConstants.jsm");

    let nssInfo = Cc["@mozilla.org/security/nssversion;1"].getService(Ci.nsINSSVersion);

    return {
        nssVersion: "NSS " + nssInfo.NSS_Version,
        nsprVersion: "NSPR " + nssInfo.NSPR_Version,
        branch: AppConstants.MOZ_UPDATE_CHANNEL,
        appVersion: AppConstants.MOZ_APP_VERSION_DISPLAY
    };
}

// Command object definition. Must be in-sync with Python world.
function Command(json_string) {
    let parsed_command = JSON.parse(json_string);
    this.id = parsed_command.id;
    this.mode = parsed_command.mode;
    this.args = parsed_command.args;
}

Command.prototype.report_result = (function _report_result(success, response) {
    // Send a response back to the python world
    print(JSON.stringify({
        "id": this.id,
        "success": success,
        "response": response
    }));
}).bind(this);

Command.prototype.handle = function _handle() {
    switch (this.mode) {
        case "info":
            this.report_result(true, get_runtime_info());
            break;
        case "useprofile":
            use_profile(this.args.path);
            this.report_result(true, "OK");
            break;
        case "updateprofile":
            set_prefs();
            update_profile();
            this.report_result(true, "OK");
            break;
        case "scan":
            scan_url(this.args.url).then(result => {
                this.report_result(true, "OK");
            }, result => {
                this.report_result(true, "FAIL: " + JSON.stringify(result));
            }).bind(this);
            break;
        case "quit":
            gScriptDone = true;
            // Intentional fall-through
        case "wakeup":
            while (mainThread.hasPendingEvents()) mainThread.processNextEvent(true);
            this.report_result(true, "OK");
            break;
        default:
            this.report_result(false, "Unknown command mode");
    }
};

// The main loop only reads and handles commands from stdin.
while (!gScriptDone) {
    let cmd = null;
    try {
        cmd = new Command(readline());
    } catch (error) {
        print(error);
        continue;
    }
    try {
        cmd.handle();
    } catch (error) {
        cmd.report_result(false, String(error));
    }
}
