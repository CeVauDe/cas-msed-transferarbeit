# Remove trailing period from section numbers (e.g. "3.2.1." → "3.2.1")
# The flag prevents stripping the delimiter from intermediate recursive calls
# that build the dots between levels (e.g. "3." in "3.2.1.").
::Asciidoctor::Section.prepend(Module.new do
  def sectnum(delimiter = '.', append = delimiter)
    if Thread.current[:sectnum_recursing]
      super
    else
      Thread.current[:sectnum_recursing] = true
      begin
        super
      ensure
        Thread.current[:sectnum_recursing] = false
      end.delete_suffix(delimiter)
    end
  end
end)
