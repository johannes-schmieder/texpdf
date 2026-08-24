*! version 0.1.0 24aug2026
program define texpdf, rclass
    version 14.1
    syntax [using/] [, SAVing(string asis) REPLACE VERSION]

    if "`version'" != "" {
        if `"`using'"' != "" | `"`saving'"' != "" | "`replace'" != "" {
            display as error "option version may not be combined with using, saving(), or replace"
            exit 198
        }

        tempfile result
        capture noisily plugin call _texpdf_plugin, version `"`result'"'
        local plugin_rc = _rc
        if `plugin_rc' {
            display as error "texpdf native plugin invocation failed (r(`plugin_rc'))"
            exit `plugin_rc'
        }
        quietly _texpdf_read_result using `"`result'"'
        local native_status `"`r(status)'"'
        local native_rc = r(rc)
        local native_message `"`r(message)'"'
        local native_diagnostics `"`r(diagnostics)'"'
        local engine `"`r(engine)'"'
        local engine_version `"`r(engine_version)'"'
        local bundle_version `"`r(bundle_version)'"'
        local bundle_digest `"`r(bundle_digest)'"'
        local bundle_zip_sha256 `"`r(bundle_zip_sha256)'"'
        local warnings = r(warnings)

        if `"`native_status'"' != "success" {
            if `"`native_message'"' != "" display as error `"`native_message'"'
            if `"`native_diagnostics'"' != "" display as error `"`native_diagnostics'"'
            if missing(`native_rc') | `native_rc' == 0 local native_rc 710
            exit `native_rc'
        }

        display as text "texpdf 0.1.0; engine " as result "Tectonic `engine_version'"
        return local engine `"`engine'"'
        return local engine_version `"`engine_version'"'
        return local bundle_version `"`bundle_version'"'
        return local bundle_digest `"`bundle_digest'"'
        return local bundle_zip_sha256 `"`bundle_zip_sha256'"'
        return scalar warnings = `warnings'
        exit
    }

    if `"`using'"' == "" {
        display as error "using filename is required"
        exit 198
    }

    local input `"`using'"'
    local output `"`saving'"'
    if `"`output'"' == "" {
        local input_length = ustrlen(`"`input'"')
        local suffix ""
        if `input_length' >= 4 {
            local suffix_start = `input_length' - 3
            local suffix = ustrlower(usubstr(`"`input'"', `suffix_start', 4))
        }
        if `"`suffix'"' == ".tex" {
            local prefix_length = `input_length' - 4
            if `prefix_length' > 0 {
                local prefix = usubstr(`"`input'"', 1, `prefix_length')
                local output `"`prefix'.pdf"'
            }
            else local output `"`input'.pdf"'
        }
        else local output `"`input'.pdf"'
    }

    local replace_flag = cond("`replace'" == "", 0, 1)
    tempfile result
    capture noisily plugin call _texpdf_plugin, compile `"`input'"' `"`output'"' `"`result'"' `replace_flag' 0
    local plugin_rc = _rc
    if `plugin_rc' {
        display as error "texpdf native plugin invocation failed (r(`plugin_rc'))"
        exit `plugin_rc'
    }

    quietly _texpdf_read_result using `"`result'"'
    local native_status `"`r(status)'"'
    local native_rc = r(rc)
    local native_message `"`r(message)'"'
    local native_diagnostics `"`r(diagnostics)'"'
    local pdf `"`r(pdf)'"'
    local engine `"`r(engine)'"'
    local engine_version `"`r(engine_version)'"'
    local bundle_version `"`r(bundle_version)'"'
    local bundle_digest `"`r(bundle_digest)'"'
    local bundle_zip_sha256 `"`r(bundle_zip_sha256)'"'
    local warnings = r(warnings)

    if `"`native_status'"' != "success" {
        if `"`native_message'"' != "" display as error `"`native_message'"'
        if `"`native_diagnostics'"' != "" display as error `"`native_diagnostics'"'
        if missing(`native_rc') | `native_rc' == 0 local native_rc 710
        exit `native_rc'
    }

    display as text "PDF written to " as result `"`pdf'"'
    return local pdf `"`pdf'"'
    return local engine `"`engine'"'
    return local engine_version `"`engine_version'"'
    return local bundle_version `"`bundle_version'"'
    return local bundle_digest `"`bundle_digest'"'
    return local bundle_zip_sha256 `"`bundle_zip_sha256'"'
    return scalar warnings = `warnings'
end

program define _texpdf_read_result, rclass
    version 14.1
    syntax using/

    capture confirm file `"`using'"'
    if _rc {
        display as error "texpdf native plugin did not create a result record"
        exit 710
    }

    tempname handle
    capture file open `handle' using `"`using'"', read text
    if _rc {
        display as error "texpdf could not open the native result record"
        exit 710
    }

    local schema_version ""
    local status ""
    local native_rc ""
    local operation ""
    local message ""
    local diagnostics ""
    local pdf ""
    local engine ""
    local engine_version ""
    local bundle_version ""
    local bundle_digest ""
    local bundle_zip_sha256 ""
    local warnings "0"
    local diagnostic_count "0"

    file read `handle' line
    while r(eof) == 0 {
        local equals = ustrpos(`"`line'"', "=")
        if `equals' > 1 {
            local key = usubstr(`"`line'"', 1, `equals' - 1)
            local value_length = ustrlen(`"`line'"') - `equals'
            local value = usubstr(`"`line'"', `equals' + 1, `value_length')

            if `"`key'"' == "schema_version" local schema_version `"`value'"'
            else if `"`key'"' == "status" local status `"`value'"'
            else if `"`key'"' == "rc" local native_rc `"`value'"'
            else if `"`key'"' == "operation" local operation `"`value'"'
            else if `"`key'"' == "message" local message `"`value'"'
            else if `"`key'"' == "pdf" local pdf `"`value'"'
            else if `"`key'"' == "engine" local engine `"`value'"'
            else if `"`key'"' == "engine_version" local engine_version `"`value'"'
            else if `"`key'"' == "bundle_version" local bundle_version `"`value'"'
            else if `"`key'"' == "bundle_digest" local bundle_digest `"`value'"'
            else if `"`key'"' == "bundle_zip_sha256" local bundle_zip_sha256 `"`value'"'
            else if `"`key'"' == "warnings" local warnings `"`value'"'
            else if `"`key'"' == "diagnostic_count" local diagnostic_count `"`value'"'
            else if regexm(`"`key'"', "^diagnostic_[0-9]+_message$") {
                if `"`diagnostics'"' == "" local diagnostics `"`value'"'
                else local diagnostics `"`diagnostics' | `value'"'
            }
        }
        file read `handle' line
    }
    file close `handle'

    if `"`schema_version'"' != "1" {
        display as error "unsupported or malformed texpdf native result record"
        exit 710
    }
    if !inlist(`"`status'"', "success", "failure") {
        display as error "malformed texpdf native status"
        exit 710
    }

    local rc_number = real(`"`native_rc'"')
    if missing(`rc_number') {
        display as error "malformed texpdf native return code"
        exit 710
    }
    local warning_number = real(`"`warnings'"')
    if missing(`warning_number') local warning_number 0
    local diagnostic_number = real(`"`diagnostic_count'"')
    if missing(`diagnostic_number') local diagnostic_number 0

    return local status `"`status'"'
    return scalar rc = `rc_number'
    return local operation `"`operation'"'
    return local message `"`message'"'
    return local diagnostics `"`diagnostics'"'
    return local pdf `"`pdf'"'
    return local engine `"`engine'"'
    return local engine_version `"`engine_version'"'
    return local bundle_version `"`bundle_version'"'
    return local bundle_digest `"`bundle_digest'"'
    return local bundle_zip_sha256 `"`bundle_zip_sha256'"'
    return scalar warnings = `warning_number'
    return scalar diagnostic_count = `diagnostic_number'
end

program define _texpdf_plugin, plugin
