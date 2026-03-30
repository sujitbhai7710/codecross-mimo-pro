/**
 * Frida Key Extraction Script for CodyCross
 * ==========================================
 * Hooks into the PuzzleCrypto class at runtime to capture the AES-256 key
 * used for decrypting puzzle data from the API.
 *
 * Target: com.fanatee.cody (Unity IL2CPP)
 * Class:  Fanatee.CodyCross.Domain.Crypto.PuzzleCrypto
 * Method: CreateDecryptor / Decrypt
 *
 * Usage:
 *   frida -U -f com.fanatee.cody -l frida-extract.js --no-pause
 *
 * Output: JSON with hex-encoded AES key written to /tmp/frida-result.json
 */

'use strict';

// Track if we've already found the key
let keyFound = false;
let capturedKeys = [];

// ============================================================
// IL2CPP CLASS RESOLVER
// ============================================================

function resolveIl2CppClass(className) {
    // Try to resolve via Il2Cpp module
    try {
        const il2cpp = Process.getModuleByName('libil2cpp.so');
        
        // Search for the class string in memory
        const classNameBytes = className.split('').map(c => c.charCodeAt(0));
        const classNamePattern = classNameBytes.map(b => 
            ('0' + b.toString(16)).slice(-2)
        ).join(' ');
        
        console.log(`[*] Searching for class: ${className}`);
        console.log(`[*] Pattern: ${classNamePattern}`);
        
        return il2cpp;
    } catch (e) {
        console.log(`[!] Failed to resolve IL2CPP: ${e}`);
        return null;
    }
}

// ============================================================
// METHOD 1: Hook Java Crypto (AES Cipher)
// ============================================================

function hookJavaAESCipher() {
    if (Java.available) {
        Java.perform(function() {
            console.log('[*] Attempting to hook javax.crypto.Cipher...');
            
            try {
                const Cipher = Java.use('javax.crypto.Cipher');
                
                // Hook doFinal to capture decrypted output
                Cipher.doFinal.overload('[B').implementation = function(input) {
                    const result = this.doFinal(input);
                    
                    if (input.length > 100) { // Only log significant decryptions
                        console.log(`[+] AES doFinal called:`);
                        console.log(`    Input: ${input.length} bytes`);
                        console.log(`    Output: ${result.length} bytes`);
                        console.log(`    Algorithm: ${this.getAlgorithm()}`);
                        
                        // Try to decode as UTF-8 to see if it's puzzle data
                        try {
                            const text = Java.use('java.lang.String').$new(result, 'UTF-8');
                            const str = text.toString();
                            if (str.indexOf('{') >= 0 || str.indexOf('puzzle') >= 0 || 
                                str.indexOf('answer') >= 0 || str.indexOf('clue') >= 0) {
                                console.log(`[+] FOUND PUZZLE DATA!`);
                                console.log(`[+] Preview: ${str.substring(0, 200)}`);
                                sendFridaResult({ type: 'puzzle_data', preview: str.substring(0, 500), size: result.length });
                            }
                        } catch (e) {}
                    }
                    
                    return result;
                };
                
                console.log('[+] javax.crypto.Cipher.doFinal hooked');
            } catch (e) {
                console.log(`[!] Failed to hook Cipher: ${e}`);
            }
            
            // Also try to hook SecretKeySpec to capture the key
            try {
                const SecretKeySpec = Java.use('javax.crypto.spec.SecretKeySpec');
                
                SecretKeySpec.$init.overload('[B', 'java.lang.String').implementation = function(keyBytes, algorithm) {
                    if (keyBytes && keyBytes.length === 32) { // AES-256
                        const keyHex = Array.from(keyBytes).map(b => 
                            ('0' + (b & 0xFF).toString(16)).slice(-2)
                        ).join('');
                        
                        console.log(`[!!!] AES-256 KEY CAPTURED!`);
                        console.log(`[!!!] Key (hex): ${keyHex}`);
                        console.log(`[!!!] Algorithm: ${algorithm}`);
                        
                        keyFound = true;
                        capturedKeys.push({
                            hex: keyHex,
                            length: keyBytes.length,
                            algorithm: algorithm
                        });
                        
                        sendFridaResult({ type: 'aes_key', key_hex: keyHex, key_length: keyBytes.length, algorithm: algorithm });
                    } else if (keyBytes && keyBytes.length === 16) { // AES-128
                        const keyHex = Array.from(keyBytes).map(b => 
                            ('0' + (b & 0xFF).toString(16)).slice(-2)
                        ).join('');
                        console.log(`[*] AES-128 key found: ${keyHex}`);
                        console.log(`[*] Algorithm: ${algorithm}`);
                        capturedKeys.push({
                            hex: keyHex,
                            length: keyBytes.length,
                            algorithm: algorithm
                        });
                    }
                    
                    return this.$init(keyBytes, algorithm);
                };
                
                console.log('[+] javax.crypto.spec.SecretKeySpec hooked');
            } catch (e) {
                console.log(`[!] Failed to hook SecretKeySpec: ${e}`);
            }

            // Hook IvParameterSpec to capture IV
            try {
                const IvParameterSpec = Java.use('javax.crypto.spec.IvParameterSpec');
                
                IvParameterSpec.$init.overload('[B').implementation = function(ivBytes) {
                    if (ivBytes && ivBytes.length === 16) {
                        const ivHex = Array.from(ivBytes).map(b => 
                            ('0' + (b & 0xFF).toString(16)).slice(-2)
                        ).join('');
                        console.log(`[*] IV captured: ${ivHex}`);
                        sendFridaResult({ type: 'aes_iv', iv_hex: ivHex });
                    }
                    return this.$init(ivBytes);
                };
                
                console.log('[+] IvParameterSpec hooked');
            } catch (e) {
                console.log(`[!] Failed to hook IvParameterSpec: ${e}`);
            }

            // Hook Cipher.init to capture full initialization
            try {
                const Cipher = Java.use('javax.crypto.Cipher');
                
                Cipher.init.overload('int', 'java.security.Key').implementation = function(mode, key) {
                    const modeStr = mode === 1 ? 'ENCRYPT' : 'DECRYPT';
                    const algo = key.getAlgorithm();
                    const keyLen = key.getEncoded().length * 8;
                    
                    console.log(`[*] Cipher.init: ${modeStr} ${algo}-${keyLen}`);
                    
                    return this.init(mode, key);
                };
                
                Cipher.init.overload('int', 'java.security.Key', 'java.security.spec.AlgorithmParameterSpec').implementation = function(mode, key, params) {
                    const modeStr = mode === 1 ? 'ENCRYPT' : 'DECRYPT';
                    const algo = key.getAlgorithm();
                    const keyLen = key.getEncoded().length * 8;
                    
                    console.log(`[*] Cipher.init: ${modeStr} ${algo}-${keyLen} with params`);
                    
                    return this.init(mode, key, params);
                };
                
                console.log('[+] Cipher.init hooked');
            } catch (e) {
                console.log(`[!] Failed to hook Cipher.init: ${e}`);
            }
        });
    } else {
        console.log('[!] Java runtime not available');
    }
}

// ============================================================
// METHOD 2: Native Hook - Scan for AES key patterns
// ============================================================

function hookNativeAES() {
    try {
        const il2cpp = Process.getModuleByName('libil2cpp.so');
        console.log(`[*] libil2cpp.so loaded at ${il2cpp.base}`);
        console.log(`[*] Size: ${il2cpp.size} bytes`);
        
        // Scan for potential AES keys (32-byte aligned constant arrays)
        // AES keys are often stored as static byte arrays in the binary
        const ranges = il2cpp.enumerateRanges('r--');
        let keyCandidates = 0;
        
        for (const range of ranges) {
            if (range.size < 32) continue;
            
            try {
                const bytes = range.base.readByteArray(Math.min(range.size, 4096));
                if (!bytes) continue;
                
                const view = new DataView(bytes);
                
                for (let offset = 0; offset < bytes.byteLength - 32; offset++) {
                    // Look for 32-byte sequences with reasonable entropy
                    // (not all zeros, not all same byte, not sequential)
                    let uniqueBytes = new Set();
                    let allPrintable = true;
                    let allZero = true;
                    
                    for (let i = 0; i < 32; i++) {
                        const b = view.getUint8(offset + i);
                        uniqueBytes.add(b);
                        if (b !== 0) allZero = false;
                        if (b < 32 || b > 126) allPrintable = false;
                    }
                    
                    // Skip all-zero, all-same, or very low entropy
                    if (allZero || uniqueBytes.size < 8) continue;
                    
                    // Log potential key candidates
                    if (uniqueBytes.size >= 20) { // High entropy = likely a key
                        keyCandidates++;
                        if (keyCandidates <= 10) {
                            const hexArr = [];
                            for (let i = 0; i < 32; i++) {
                                hexArr.push(('0' + view.getUint8(offset + i).toString(16)).slice(-2));
                            }
                            console.log(`[?] Key candidate #${keyCandidates} at ${range.base.add(offset)}: ${hexArr.join('')}`);
                            
                            if (allPrintable) {
                                const ascii = [];
                                for (let i = 0; i < 32; i++) {
                                    ascii.push(String.fromCharCode(view.getUint8(offset + i)));
                                }
                                console.log(`    ASCII: ${ascii.join('')}`);
                            }
                        }
                    }
                }
            } catch (e) {}
        }
        
        console.log(`[*] Found ${keyCandidates} potential AES key candidates in binary`);
        
    } catch (e) {
        console.log(`[!] Native hook failed: ${e}`);
    }
}

// ============================================================
// METHOD 3: Hook Unity's AES implementation directly
// ============================================================

function hookUnityAES() {
    try {
        const il2cpp = Process.getModuleByName('libil2cpp.so');
        
        // Try to find and hook common AES patterns
        // Unity games often use their own AES implementation or wrap BouncyCastle
        
        const exports = il2cpp.enumerateExports();
        const aesExports = [];
        
        for (const exp of exports) {
            const name = exp.name.toLowerCase();
            if (name.includes('aes') || name.includes('crypt') || 
                name.includes('decrypt') || name.includes('cipher') ||
                name.includes('rijndael') || name.includes('puzzlecrypto')) {
                aesExports.push(exp);
            }
        }
        
        console.log(`\n[*] Found ${aesExports.length} crypto-related exports:`);
        aesExports.slice(0, 30).forEach(exp => {
            console.log(`    ${exp.type} ${exp.name} @ ${exp.address}`);
        });
        
        // Hook specific exports related to PuzzleCrypto
        for (const exp of aesExports) {
            const name = exp.name.toLowerCase();
            if ((name.includes('puzzlecrypto') || name.includes('puzzle_crypto')) && 
                exp.type === 'function') {
                console.log(`[*] Hooking PuzzleCrypto function: ${exp.name}`);
                try {
                    Interceptor.attach(exp.address, {
                        onEnter: function(args) {
                            console.log(`[+] PuzzleCrypto.${exp.name} called`);
                            // Dump first few args as hex
                            for (let i = 0; i < 4; i++) {
                                try {
                                    const buf = Memory.readByteArray(args[i], 32);
                                    const hex = Array.from(new Uint8Array(buf)).map(b => 
                                        ('0' + b.toString(16)).slice(-2)
                                    ).join(' ');
                                    console.log(`    arg${i}: ${hex}`);
                                } catch (e) {}
                            }
                        },
                        onLeave: function(retval) {
                            console.log(`[+] PuzzleCrypto.${exp.name} returned`);
                        }
                    });
                } catch (e) {
                    console.log(`[!] Failed to hook ${exp.name}: ${e}`);
                }
            }
        }
        
    } catch (e) {
        console.log(`[!] Unity AES hook failed: ${e}`);
    }
}

// ============================================================
// METHOD 4: Hook via IL2CPP internal APIs
// ============================================================

function hookIl2CppInternals() {
    try {
        const il2cpp = Process.getModuleByName('libil2cpp.so');
        
        // Find il2cpp_resolve_icall or similar to intercept crypto calls
        const resolve_icall = Module.findExportByName('libil2cpp.so', 'il2cpp_resolve_icall');
        if (resolve_icall) {
            Interceptor.attach(resolve_icall, {
                onEnter: function(args) {
                    const name = args[0].readCString();
                    if (name && (name.includes('Crypt') || name.includes('AES') || 
                                 name.includes('Rijndael') || name.includes('Decrypt'))) {
                        console.log(`[IL2CPP] Resolved icall: ${name}`);
                    }
                }
            });
            console.log('[+] il2cpp_resolve_icall hooked');
        }
        
        // Try to find string literal containing crypto-related keys
        // In IL2CPP, string literals are stored in global-metadata.dat and loaded at runtime
        const load_from_metadata = Module.findExportByName('libil2cpp.so', 'il2cpp_string_literal_get');
        if (load_from_metadata) {
            let strCount = 0;
            Interceptor.attach(load_from_metadata, {
                onLeave: function(retval) {
                    try {
                        if (!retval.isNull()) {
                            // Unity strings have a length prefix
                            const lengthPtr = retval.sub(16).readS32();
                            if (lengthPtr > 8 && lengthPtr < 256) {
                                const chars = retval.readUtf16String(lengthPtr);
                                if (chars) {
                                    const lower = chars.toLowerCase();
                                    if (lower.includes('aes') || lower.includes('key') || 
                                        lower.includes('crypt') || lower.includes('secret') ||
                                        lower.includes('puzzle') && lower.includes('key')) {
                                        console.log(`[String] "${chars}" (len=${lengthPtr})`);
                                        strCount++;
                                    }
                                }
                            }
                        }
                    } catch(e) {}
                }
            });
            console.log('[+] il2cpp_string_literal_get hooked');
        }
        
    } catch(e) {
        console.log(`[!] IL2CPP internal hook failed: ${e}`);
    }
}

// ============================================================
// RESULT SENDING
// ============================================================

function sendFridaResult(result) {
    const json = JSON.stringify(result);
    console.log(`[RESULT] ${json}`);
    
    // Write to file for CI to pick up
    try {
        const fopen = new NativeFunction(Module.getExportByName(null, 'fopen'), 'pointer', ['pointer', 'pointer']);
        const fputs = new NativeFunction(Module.getExportByName(null, 'fputs'), 'int', ['pointer', 'pointer']);
        const fclose = new NativeFunction(Module.getExportByName(null, 'fclose'), 'int', ['pointer']);
        
        const pathStr = Memory.allocUtf8String('/tmp/frida-result.json');
        const modeStr = Memory.allocUtf8String('w');
        const jsonStr = Memory.allocUtf8String(json);
        
        const fp = fopen(pathStr, modeStr);
        if (!fp.isNull()) {
            fputs(jsonStr, fp);
            fclose(fp);
            console.log('[+] Result written to /tmp/frida-result.json');
        }
    } catch(e) {
        console.log(`[!] Could not write result file: ${e}`);
    }
}

// ============================================================
// MAIN
// ============================================================

console.log('========================================');
console.log('  CodyCross AES Key Extractor (Frida)');
console.log('  Target: com.fanatee.cody v2.8.1');
console.log('========================================\n');

// Wait for the app to fully load
setTimeout(function() {
    console.log('\n[*] Starting hooks after app load...\n');
    
    // Method 1: Hook Java crypto APIs
    hookJavaAESCipher();
    
    // Method 2: Scan binary for key patterns  
    hookNativeAES();
    
    // Method 3: Hook Unity AES implementation
    hookUnityAES();
    
    // Method 4: Hook IL2CPP internals
    hookIl2CppInternals();
    
    // Auto-trigger: simulate app interactions to force puzzle loading
    if (Java.available) {
        Java.perform(function() {
            try {
                // Get the main activity and trigger puzzle navigation
                // This will force the app to decrypt puzzle data
                const ActivityThread = Java.use('android.app.ActivityThread');
                const app = ActivityThread.currentApplication();
                
                console.log(`[+] App context: ${app.getPackageName()}`);
                console.log(`[+] Waiting for puzzle decryption to trigger...`);
                console.log(`[*] The hooks above will capture the key when any puzzle is loaded`);
                console.log(`[*] You can navigate in the app to trigger puzzle loading`);
            } catch(e) {
                console.log(`[!] Could not get app context: ${e}`);
            }
        });
    }
    
}, 3000); // Wait 3 seconds for app initialization

// Also send periodic status updates for CI
setInterval(function() {
    if (capturedKeys.length > 0 && !keyFound) {
        keyFound = true;
        console.log(`\n[!!!] EXTRACTION COMPLETE!`);
        console.log(`[!!!] Found ${capturedKeys.length} key(s):`);
        capturedKeys.forEach((k, i) => {
            console.log(`    Key ${i+1}: ${k.hex} (${k.algorithm || 'unknown'})`);
        });
        
        // Send final result
        sendFridaResult({
            type: 'extraction_complete',
            keys: capturedKeys
        });
    }
}, 2000);
